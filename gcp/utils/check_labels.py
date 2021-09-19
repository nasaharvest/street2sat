from google.cloud import storage
import re

# https://cloud.google.com/sdk/docs/install
# https://googleapis.dev/python/storage/latest/buckets.html


def multiple_replace(dict, text):
    # Create a regular expression  from the dictionary keys
    regex = re.compile("(%s)" % "|".join(map(re.escape, dict.keys())))
    return regex.sub(lambda mo: dict[mo.string[mo.start():mo.end()]], text)

def main():
    client = storage.Client()
    bucket = client.get_bucket('street2sat-model-labeled-data')

    # TODO: determine from yaml file 
    imgs_train_prefix = 'run2/images/train/'
    imgs_val_prefix = 'run2/images/val/'
    labels_train_prefix = 'run2/labels/train/'
    labels_val_prefix = 'run2/labels/val/'

    data_prefixes = [imgs_train_prefix, labels_train_prefix, imgs_val_prefix, labels_val_prefix]

    # rules to clean file names
    dict = {
        imgs_train_prefix : '',
        imgs_val_prefix : '',
        labels_train_prefix : '',
        labels_val_prefix : '',
        '.txt' : '',
        '.TXT' : '',
        '.jpg' : '',
        '.jpeg' : '',
        '.JPG' : '',
        '.JPEG' : ''
    }

    # store the file names
    file_names = {}
    for pfx in data_prefixes:
        files = list(bucket.list_blobs(prefix=pfx))
        file_names[pfx] = [multiple_replace(dict, x.name) for x in files]

    print('Found:\n {} training images\n {} validation images\n {} training labels\n {} validation labels\n'.format(len(file_names[imgs_train_prefix]), len(file_names[imgs_val_prefix]), len(file_names[labels_train_prefix]), len(file_names[labels_val_prefix ])))

    # check for duplicates within each folder
    for pfx in file_names.keys():
        dups = set()
        for file in file_names[pfx]:
            if file in dups:
                print('DUPLICATE FOUND: {}'.format(pfx + file))

    # check in imgs but not in labels
    train_extra = set(file_names[imgs_train_prefix]) - set(file_names[labels_train_prefix])
    val_extra = set(file_names[imgs_val_prefix]) - set(file_names[labels_val_prefix])
    if train_extra != set():
        print("These IMAGES from training did not have a corresponding label: ")
        for img in train_extra:
            print(img)
    if val_extra != set():
        print("These IMAGES from validation did not have a corresponding label: ")
        for img in val_extra:
            print(img)

    # check in labels but not in images
    train_extra = set(file_names[labels_train_prefix]) - set(file_names[imgs_train_prefix])
    val_extra = set(file_names[labels_val_prefix]) - set(file_names[imgs_val_prefix])
    if train_extra != set():
        print("These LABELS from training did not have a corresponding image: ")
        for img in train_extra:
            print(img)
    if val_extra != set():
        print("These LABELS from validation did not have a corresponding image: ")
        for img in val_extra:
            print(img)

'''
Usage:
python check_labels.py

Must be authenticated on gcloud
'''
if __name__ == "__main__":
    main()
