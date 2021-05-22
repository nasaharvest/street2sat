
import cv2
import os
# import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import io
import base64
from .exif_utils import *
import exifread
from statistics import mean
import time
import math

# import torchaudio

# from .dl_model import raga_resnet
def predict(img_dir, save_dir):
    command = 'python yolov5/detect.py --weights model_weights/best.pt --nosave --source {} --save-txt --save-conf --project {}'.format(img_dir, save_dir)
    os.system(command)

def get_image(image_path):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    s = io.BytesIO()
    fig = Figure()
    ax = fig.subplots()
    ax.imshow(img)
    ax.axis('off')
    fig.savefig(s, format='png')
    s = base64.b64encode(s.getbuffer()).decode("ascii")
    return s


def plot_labels(image_path, label_path):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    dh, dw, _ = img.shape

    fl = open(label_path, 'r')
    data = fl.readlines()
    fl.close()

    for dt in data:

        # Split string to float
        _, x, y, w, h, _ = map(float, dt.split(' '))

        # Taken from https://github.com/pjreddie/darknet/blob/810d7f797bdb2f021dbe65d2524c2ff6b8ab5c8b/src/image.c#L283-L291
        # via https://stackoverflow.com/questions/44544471/how-to-get-the-coordinates-of-the-bounding-box-in-yolo-object-detection#comment102178409_44592380
        l = int((x - w / 2) * dw)
        r = int((x + w / 2) * dw)
        t = int((y - h / 2) * dh)
        b = int((y + h / 2) * dh)

        if l < 0:
            l = 0
        if r > dw - 1:
            r = dw - 1
        if t < 0:
            t = 0
        if b > dh - 1:
            b = dh - 1

        cv2.rectangle(img, (l, t), (r, b), (0, 0, 255), 5)

    s = io.BytesIO()
    fig = Figure()
    ax = fig.subplots()
    ax.imshow(img)
    ax.axis('off')
    fig.savefig(s, format='png')
    s = base64.b64encode(s.getbuffer()).decode("ascii")
    return s


def get_height_pixels(image_path, label_path):
    img = cv2.imread(image_path)
    dh, dw, _ = img.shape

    fl = open(label_path, 'r')
    data = fl.readlines()
    fl.close()
    all_h = {}
    for dt in data:

        # Split string to float
        c, x, y, w, h, _ = map(float, dt.split(' '))

        c = int(c)
        if c in all_h.keys():
            all_h[c].append(h * dh)
        else:
            all_h[c] = [h * dh]

    return all_h


def get_distance_meters(image_path, label_path):
    GOPRO_SENSOR_HEIGHT = 4.55

    f = open(image_path, 'rb')
    tags = exifread.process_file(f)
    focal_length = get_exif_focal_length(tags)
    pixel_height, pixel_width = get_exif_image_height_width(tags)
    lat_long = get_exif_location(tags)
    heights = {}
    with open('flask_app/static/heights.txt') as heights_file:
        for line in heights_file:
            heights[line.split()[0]] = float(line.split()[1])
    classes = {}
    with open('flask_app/static/classes.txt') as classes_file:
        for i,line in enumerate(classes_file):
            classes[i] = line.strip()

    detected_heights = get_height_pixels(image_path, label_path)

    dict_info = {}
    for crop_index in detected_heights.keys():
        crop_name = classes[crop_index]
        typical_crop_height = heights[crop_name]
        all_dist = []
        for plant_height in detected_heights[crop_index]:
            dist = (focal_length * typical_crop_height * pixel_height) / (plant_height * GOPRO_SENSOR_HEIGHT)
            dist = dist / 1000
            all_dist.append(dist)
        dict_info[crop_name] = str(round(mean(all_dist), 3)) + ' meters'
    return dict_info

def point_meters_away(original_coord, heading, meters_dict):
    # https://stackoverflow.com/a/7835325
    new_p_dict = {}
    for crop, meters in meters_dict.items():
        R = 6378.1 #Radius of the Earth
        brng = math.radians(heading) #Bearing isdegrees converted to radians.
        meters = float(meters.split(' ')[0])
        d = meters / 1000 #Distance in km

        lat1 = math.radians(original_coord[0]) #Current lat point converted to radians
        lon1 = math.radians(original_coord[1]) #Current long point converted to radians

        lat2 = math.asin( math.sin(lat1)*math.cos(d/R) + math.cos(lat1)*math.sin(d/R)*math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1),math.cos(d/R)-math.sin(lat1)*math.sin(lat2))

        lat2 = math.degrees(lat2)
        lon2 = math.degrees(lon2)

        new_p_dict[crop] = (lat2, lon2)

    return new_p_dict


def get_new_points(time_dict, coord_dict, distance_dict):
    # find closest point in time
    # find heading by doing coordinate at closest point and current point 90 degrees left
    # add distance to current point
    bearings = {}
    for time_val,file in time_dict.items():
        all_times = list(time_dict.keys())
        all_times.remove(time_val)
        closest_time = min(all_times, key=lambda d: abs(time.mktime(d) - time.mktime(time_val)))

        file_with_closest_time = time_dict[closest_time]
        original_coord = coord_dict[file]
        closest_coord = coord_dict[file_with_closest_time]

        # taken from https://gist.github.com/jeromer/2005586
        lat1 = math.radians(original_coord[0])
        lat2 = math.radians(closest_coord[0])

        diffLong = math.radians(closest_coord[1] - original_coord[1])

        x = math.sin(diffLong) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
                * math.cos(lat2) * math.cos(diffLong))

        initial_bearing = math.atan2(x, y)
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360

        if time.mktime(closest_time) < time.mktime(time_val):
            compass_bearing = (compass_bearing + 180) % 360

        ##### IMPORTANT ASSUMPTION ALL CAMERAS POINT LEFT ####
        bearings[file] = (compass_bearing - 90) % 360

    # file:crop:(lat,long)
    new_points = {}
    for file, bearing in bearings.items():
        if file in distance_dict.keys():
            distance_meters = distance_dict[file]
            translated_coords = point_meters_away(coord_dict[file], bearing, distance_meters)
            new_points[file] = translated_coords

    return bearings, new_points

## -- Example usage -- ###
if __name__ == "__main__":
    import os
    predict('../temp/uQBYaAsIgV/', '../temp/uQBYaAsIgV/')




#
# def predict(ex_file, state_dict_path = './model_weights/trained_modelamplitude_added_and_lower_mels_resnet18.tar'):
#     label_to_name = {0: 'AbhEri', 1: 'shuddhadhanyAsi'}
#
#     model = raga_resnet('cpu', num_ragas = 2)
#     device = torch.device('cpu')
#     model.load_state_dict(torch.load(state_dict_path, map_location=device))
#     model.eval()
#
#     waveform, sample_rate = torchaudio.load(ex_file)
#     if len(waveform.shape) > 1:
#         waveform = waveform.mean(axis = 0).reshape((1,-1))
#     len_index_30_sec = int(30 / (1 / sample_rate))
#     # trim first and last 30 seconds if long enough
#     if waveform.shape[1] > 2 * len_index_30_sec:
#         waveform = waveform[:, len_index_30_sec:-len_index_30_sec]
#         # get random start index
#         start_index = np.random.randint(low = 0, high = waveform.shape[1] - len_index_30_sec)
#         waveform = waveform[:, start_index:start_index + 2*(len_index_30_sec)]
#     else:
#         waveform = waveform[:,0: 2 * len_index_30_sec]
#         print('too short', waveform.shape, sample_rate)
#     effects = [
#             [ "rate", "44100"]
#             ]
#     waveform, sample_rate = torchaudio.sox_effects.apply_effects_tensor(
#         waveform, sample_rate, effects)
#     len_index_30_sec = int(30 / (1 / sample_rate))
#     waveform = waveform[:, 0:len_index_30_sec]
#
#
#     with torch.no_grad():
#         vals = model(waveform.unsqueeze(0)).squeeze()
#         # print(vals)
#         return label_to_name[int(torch.argmax(vals))]
#
#
#

# import requests
#
#
# class Movie(object):
#     def __init__(self, omdb_json, detailed=False):
#         if detailed:
#             self.genres = omdb_json["Genre"]
#             self.director = omdb_json["Director"]
#             self.actors = omdb_json["Actors"]
#             self.plot = omdb_json["Plot"]
#             self.awards = omdb_json["Awards"]
#
#         self.title = omdb_json["Title"]
#         self.year = omdb_json["Year"]
#         self.imdb_id = omdb_json["imdbID"]
#         self.type = "Movie"
#         self.poster_url = omdb_json["Poster"]
#
#     def __repr__(self):
#         return self.title
#
#
# class MovieClient(object):
#     def __init__(self, api_key):
#         self.sess = requests.Session()
#         self.base_url = f"http://www.omdbapi.com/?apikey={api_key}&r=json&type=movie&"
#
#     def search(self, search_string):
#         """
#         Searches the API for the supplied search_string, and returns
#         a list of Media objects if the search was successful, or the error response
#         if the search failed.
#
#         Only use this method if the user is using the search bar on the website.
#         """
#         search_string = "+".join(search_string.split())
#         page = 1
#
#         search_url = f"s={search_string}&page={page}"
#
#         resp = self.sess.get(self.base_url + search_url)
#
#         if resp.status_code != 200:
#             raise ValueError(
#                 "Search request failed; make sure your API key is correct and authorized"
#             )
#
#         data = resp.json()
#
#         if data["Response"] == "False":
#             raise ValueError(f'[ERROR]: Error retrieving results: \'{data["Error"]}\' ')
#
#         search_results_json = data["Search"]
#         remaining_results = int(data["totalResults"])
#
#         result = []
#
#         ## We may have more results than are first displayed
#         while remaining_results != 0:
#             for item_json in search_results_json:
#                 result.append(Movie(item_json))
#                 remaining_results -= len(search_results_json)
#             page += 1
#             search_url = f"s={search_string}&page={page}"
#             resp = self.sess.get(self.base_url + search_url)
#             if resp.status_code != 200 or resp.json()["Response"] == "False":
#                 break
#             search_results_json = resp.json()["Search"]
#
#         return result
#
#     def retrieve_movie_by_id(self, imdb_id):
#         """
#         Use to obtain a Movie object representing the movie identified by
#         the supplied imdb_id
#         """
#         movie_url = self.base_url + f"i={imdb_id}&plot=full"
#
#         resp = self.sess.get(movie_url)
#
#         if resp.status_code != 200:
#             raise ValueError(
#                 "Search request failed; make sure your API key is correct and authorized"
#             )
#
#         data = resp.json()
#
#         if data["Response"] == "False":
#             raise ValueError(f'Error retrieving results: \'{data["Error"]}\' ')
#
#         movie = Movie(data, detailed=True)
#
#         return movie
#
#


    # client = MovieClient(os.environ.get("OMDB_API_KEY"))

    # movies = client.search("guardians")

    # for movie in movies:
        # print(movie)

    # print(len(movies))
