from google.cloud import storage
import re

# count the number of boxes from a txt string
def count_from_txt(txt):
    # labels are stored as integers
    counts = {}
    for line in txt.splitlines():
        l = line.split()
        if int(l[0]) not in counts.keys():
            counts[int(l[0])] = 1
        else:
            counts[int(l[0])] = counts[int(l[0])] + 1
    return counts

def main():
    client = storage.Client()
    bucket = client.get_bucket('street2sat-model-labeled-data')

    labels_train_prefix = 'run2/labels/train/'
    labels_val_prefix = 'run2/labels/val/'

    train_counts = {}
    for file in bucket.list_blobs(prefix=labels_train_prefix):
        counts = count_from_txt(file.download_as_string())
        train_counts = {k: train_counts.get(k, 0) + counts.get(k, 0) for k in set(train_counts) | set(counts)}

    val_counts = {}
    for file in bucket.list_blobs(prefix=labels_val_prefix):
        counts = count_from_txt(file.download_as_string())
        val_counts = {k: val_counts.get(k, 0) + counts.get(k, 0) for k in set(val_counts) | set(counts)}

    print('TRAIN:')
    print(train_counts)

    print("VALIDATION:")
    print(val_counts)


'''
Usage:
python count_labels.py

Must be authenticated on gcloud 
'''
if __name__ == "__main__":
    main()
