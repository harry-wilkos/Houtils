<h1 align="center">Houtils</h1>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=for-the-badge" height="40" alt="python logo"  />
  <img width="12" />
  <img src="https://img.shields.io/badge/Houdini-FF4713?style=for-the-badge&logo=houdini&logoColor=white" height="40" alt="houdini logo" />
</div>


###

<h4 align="center">Houdini Tools, HDAs, Tweaks and Librarys for a more convenient experience</h4>

###

## Features
#### Tools:
+ **Recook** tool to force nodes to re-run with <*Ctrl + R*>
+ **Update Mode Toggle** with <*M*> plus visual feedback in network pane 
+ **Reload Modules** to continue writing python without restarting Houdini

#### HDAs:
+ **Error Switch** to auto-toggle inputs based on available inputs
+ Modified **Pop Source** to include an option to interpolate the emission
+ Move and rotate any object in any position to the the aligned center with **Align to Center**

#### Tweks:
+ Automatically format nodes starting with *In* or *Out*
+ Persisten *scene graph layers* panel folds 

#### Python Modules:
+ Run functions in non-blocking parallel from within Houdini
+ Use the Network Pane to display notifications



## Requirements
+ Houdini >= 20.5
  + Python >= 3.10
  + PySide2
>[!IMPORTANT]
>Houtils was built on and for Linux. While I am unaware of any comptaibilty issues and everything is built to be OS agnostic, other OSs may have issues.


## Installation

### Step 1:
Clone the repo with the below command
```bash
git clone https://github.com/harry-wilkos/Houtils.git
```

### Step 2:
From the Houtils folder, copy the `packages` folder to your Houdini user preferences folder. If there's a already a packages folder, feel free to merge the contents.
>[!TIP]
>To find the Houdini user preferences folder, paste the following command into the Python Shell Pane in Houdini.
>```python
>hou.getenv("HOUDINI_USER_PREF_DIR")
>```

### Step 3:
Edit the `houtils.json` file in the `packages` folder and change the *HOUTILS* entry to the location of the cloned repo

>[!IMPORTANT]
>If working with the [parallel](https://github.com/harry-wilkos/Houtils/blob/main/python/houtils/utils/parallel.py) module, some systems refuse to honour the executable stack requested (but seemingly un-needed) by `$HFS/dsolib/libHoudiniUT.so`. To fix this, clear the executable flag on that file. Linux users can achieve with the `execstack -c` followed by the path to the library. Do at your own risk.



## Update
If you want to update when new tools and features are added run the following two commands when in the cloned repo
```bash
git fetch --all
git reset --hard origin/main
```
