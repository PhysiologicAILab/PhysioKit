# **Overview of PhysioKit**
PhysioKit is a novel physiological computing toolkit which is open-source, accessible and affordable. HCI hobbyists and practitioners can easily access physiological sensing channels that help monitor our physiological signatures and vital signs including heart rate, heart rate variability, breathing rate, electrodermal activities. The toolkit works with a low-cost micro-controller such as Arduino. Currently, it supports acquiring EDA, Resp and PPG using any low-cost Arduino board.

PhysioKit consists of (i) a sensor and hardware layer that can be configured in a modular manner along with research needs, (ii) a software application layer that enables real-time data collection, streaming and visualization for both single and multi-user experiments. This also supports basic visual biofeedback configurations and multi-signal synchronization for co-located or remote multi-user settings.

Below figure shows architecture of PhysioKit:
<p align="left">
<img src="images/architecture.png" alt="Architecture of PhysioKit" width="1024"/>
</p>

## **Installation**
Clone the repository or Download and unzip the package.

Open terminal at the folder where the repository is located.

If you are using Python virtual environment, activate the same or create new

Install necessary Python packages: 
``` bash
pip install -r requirements.txt
```

## **Usage Instructions**
### **Step-1: Upload program on the Arduino board**
Connect the Arduino board that you want to use. At this stage the sensors need not be connected.
Navigate to "arduino/Uno" folder and as per the number of sensors that you want to use, go to the respective folder and open  the ".ino" file using Arduino IDE
For example, if you want to use all three supported sensors, you may choose "EDA_Resp_PPG" folder and open "EDA_Resp_PPG.ino"
Upload the Arduino program using IDE. If you are unfamiliar with this step, you may have a look at [this](https://support.arduino.cc/hc/en-us/articles/4733418441116-Upload-a-sketch-in-Arduino-IDE) tutorial for detailed instructions on how to upload program on Arduino board.

### **Step-2: Updating Software Configurartion File**


### **Step-3: Updating Experiment Configurartion File**


### **Step-4: Launching the PhysioKit Interface**
Run the following command 
``` bash
python main.py --config <path of config file>
see example below 
python main.py --config configs/Uno/sw_config.json
```

This shall open user interface, basic functioning of which is shown in this demo:
<p align="left">
    <img src="images/PhysioKitDemo.gif" alt="Demo of PhysioKit" width="1024"/>
</p>


### **Citing PhysioKit**
