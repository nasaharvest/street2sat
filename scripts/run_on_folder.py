import os

"""
Script to easily run detections on folder. Modify as needed. 
"""

command = (
    "python /gpfs/data1/cmongp1/mpaliyam/street2sat/yolov5/detect.py "
    "--weights /gpfs/data1/cmongp1/mpaliyam/street2sat/yolov5/runs/train/exp18/weights/best.pt "
    "--source '/gpfs/data1/cmongp1/mpaliyam/street2sat/data/uploaded_folder/2021-06-17_NACCRI-Catherine/{0}/{1}/**.jpg' "
    "--save-crop "
    "--save-txt "
    "--save-conf "
    "--conf-thres .15 "
    "--iou-thres .15 "
    "--project /gpfs/data1/cmongp1/mpaliyam/street2sat/data/NACCRI-Catherine/{0} "
    "--name {1}"
)

l = [
    ("stereo1", "114GOPRO"),
    ("stereo1", "115GOPRO"),
    ("stereo1", "116GOPRO"),
    ("stereo1", "117GOPRO"),
    ("stereo1", "118GOPRO"),
    ("stereo1", "119GOPRO"),
    ("stereo1", "120GOPRO"),
    ("stereo2", "118GOPRO"),
    ("stereo2", "119GOPRO"),
    ("stereo2", "120GOPRO"),
    ("stereo2", "121GOPRO"),
    ("stereo2", "122GOPRO"),
    ("stereo2", "123GOPRO"),
    ("stereo2", "124GOPRO"),
    ("stereo2", "125GOPRO"),
]


for i, j in l:
    print(command.format(i, j))
    os.system(command.format(i, j))
