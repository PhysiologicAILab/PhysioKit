# Data Analysis Helper

### Step-1: Preparing the data and the configuration file
Sample data and corresponding exp_config.json file is provided to illustrate how to specify the data to be analysed in the configuration file. It is crucial to provide the sampling rate (fs) and total_duration as per that used for data acquisition. Rest of the parameters are self-explanatory, though we will be preparing detailed tutorials and sharing the links to tutorial videos here.

### Step-2: Batch processing to compute metrics from PPG and EDA signals:

``` bash
physiokit_analyze --config exp_config.json --datapath sample_data --opt 0
```

### Step-3: Saving and exporting data-tables

Following command is to illustrate the use when a specific window size and step size is used, i.e. "W65_S10_nk_OptPPG".

Please specify the appropriate path for "analysis_dict_nk.npy" - as it would have been saved after executing the "Step-1".

``` bash
physiokit_analyze --config exp_config.json --datadict analysis/W120_S5__OptPPG/analysis_dict_nk.npy --opt 1
```