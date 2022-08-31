import re

from google.cloud import storage

# https://cloud.google.com/sdk/docs/install
# https://googleapis.dev/python/storage/latest/buckets.html


def multiple_replace(d, text):
    # Create a regular expression  from the dictionary keys
    regex = re.compile("(%s)" % "|".join(map(re.escape, d.keys())))
    return regex.sub(lambda mo: d[mo.string[mo.start() : mo.end()]], text)


def main():
    client = storage.Client()
    bucket = client.get_bucket("street2sat-model-labeled-data")

    # TODO: determine from yaml file
    imgs_train_prefix = "run2/images/train/"
    imgs_val_prefix = "run2/images/val/"
    labels_train_prefix = "run2/labels/train/"
    labels_val_prefix = "run2/labels/val/"

    data_prefixes = [
        imgs_train_prefix,
        labels_train_prefix,
        imgs_val_prefix,
        labels_val_prefix,
    ]

    # rules to clean file names
    dict_file_extentions = {
        imgs_train_prefix: "",
        imgs_val_prefix: "",
        labels_train_prefix: "",
        labels_val_prefix: "",
        ".txt": "",
        ".TXT": "",
        ".jpg": "",
        ".jpeg": "",
        ".JPG": "",
        ".JPEG": "",
    }

    # store the file names
    file_names = {}
    for pfx in data_prefixes:
        files = list(bucket.list_blobs(prefix=pfx))
        file_names[pfx] = [
            multiple_replace(dict_file_extentions, x.name) for x in files
        ]

    print(
        f"Found:\n {len(file_names[imgs_train_prefix])} training images\n {len(file_names[imgs_val_prefix])} validation images\n {len(file_names[labels_train_prefix])} training labels\n {len(file_names[labels_val_prefix ])} validation labels\n"
    )

    # check for duplicates within each folder
    for pfx in file_names.keys():
        dups = set()
        for file in file_names[pfx]:
            if file in dups:
                print(f"DUPLICATE FOUND: {pfx + file}")

    # check in imgs but not in labels
    train_extra = set(file_names[imgs_train_prefix]) - set(
        file_names[labels_train_prefix]
    )
    val_extra = set(file_names[imgs_val_prefix]) - set(file_names[labels_val_prefix])
    if len(train_extra) > 0:
        print("These IMAGES from training did not have a corresponding label: ")
        for img in train_extra:
            print(img)
    if len(val_extra) > 0:
        print("These IMAGES from validation did not have a corresponding label: ")
        for img in val_extra:
            print(img)

    # check in labels but not in images
    train_extra = set(file_names[labels_train_prefix]) - set(
        file_names[imgs_train_prefix]
    )
    val_extra = set(file_names[labels_val_prefix]) - set(file_names[imgs_val_prefix])
    if len(train_extra) > 0:
        print("These LABELS from training did not have a corresponding image: ")
        for img in train_extra:
            print(img)
    if len(val_extra) > 0:
        print("These LABELS from validation did not have a corresponding image: ")
        for img in val_extra:
            print(img)


"""
Usage:
python check_labels.py

Must be authenticated on gcloud
"""
if __name__ == "__main__":
    main()
