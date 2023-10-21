import csv
import numpy as np

def load_numpy_data(filepath):
    data = np.load(filepath)
    return data


def load_csv_data_all(filepath):
    eda = []
    resp = []
    ppg1 = []
    ppg2 = []
    event_code = []
    skip_first = True
    with open(filepath, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for ln in csvreader:
            if skip_first:
                # print(ln)
                skip_first = False
            else:
                # print(ln)
                # break
                eda.append(float(ln[0]))
                resp.append(float(ln[1]))
                ppg1.append(-1*float(ln[2]))
                ppg2.append(-1*float(ln[3]))
                if ln[4] != '':
                    event_code.append(float(ln[4]))
                else:
                    event_code.append(-1)

    eda = np.array(eda)
    resp = np.array(resp)
    ppg1 = np.array(ppg1)
    ppg2 = np.array(ppg2)
    event_code = np.array(event_code)
    csvfile.close()
    return eda, resp, ppg1, ppg2, event_code


def load_csv_data_ppg(filepath):
    ppg1 = []
    ppg2 = []
    event_code = []
    skip_first = True
    with open(filepath, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for ln in csvreader:
            if skip_first:
                print(ln)
                skip_first = False
            else:
                # print(ln)
                # break
                ppg1.append(-1*float(ln[2]))
                ppg2.append(-1*float(ln[3]))
                if ln[4] != '':
                    event_code.append(float(ln[4]))
                else:
                    event_code.append(-1)

    ppg1 = np.array(ppg1)
    ppg2 = np.array(ppg2)
    event_code = np.array(event_code)
    csvfile.close()
    return ppg1, ppg2, event_code


def load_csv_data_eda(filepath):
    eda = []
    event_code = []
    skip_first = True
    with open(filepath, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for ln in csvreader:
            if skip_first:
                print(ln)
                skip_first = False
            else:
                # print(ln)
                # break
                eda.append(float(ln[0]))
                if ln[4] != '':
                    event_code.append(float(ln[4]))
                else:
                    event_code.append(-1)

    eda = np.array(eda)
    event_code = np.array(event_code)
    csvfile.close()

    return eda, event_code


def load_csv_data_resp(filepath):
    resp = []
    event_code = []
    skip_first = True
    with open(filepath, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for ln in csvreader:
            if skip_first:
                print(ln)
                skip_first = False
            else:
                # print(ln)
                # break
                resp.append(float(ln[1]))
                if ln[4] != '':
                    event_code.append(float(ln[4]))
                else:
                    event_code.append(-1)

    resp = np.array(resp)
    event_code = np.array(event_code)
    csvfile.close()

    return resp, event_code

