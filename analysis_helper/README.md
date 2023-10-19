# Data Analysis Helper

### Step-1: Batch processing to compute metrics from PPG and EDA signals:

``` bash
python -m analysis_helper.process_signals --config analysis_helper/exp_config.json --datapath analysis_helper sample_data --opt 0
```

### Step-2: Saving and exporting data-tables

Following command is to illustrate the use when a specific window size and step size is used, i.e. "W65_S10_nk_OptPPG".

Please specify the appropriate path for "analysis_dict_nk.npy" - as it would have been saved after executing the "Step-1".

``` bash
python -m analysis_helper.process_signals --config analysis_helper/exp_config.json --datadict analysis/W120_S5__OptPPG/analysis_dict_nk.npy --opt 1
```