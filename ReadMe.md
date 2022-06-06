# ros_roi_publisher
ROS package to enable interactive Region of Interest publishing to ROS via OpenCV

<img src="/.images/test.gif" width="640">

## Usage
Clone this repo to your `catkin_ws/src`.  
Then from `catkin_ws` run `catkin_make`.

Source your workspace with:
```
source ~/catkin_ws/devel/setup.bash
```

Adjust the config file in `ros_roi_publisher/config` for your topic names and other parameters.

Launch the node with:
```
roslaunch ros_roi_publisher ros_roi_publisher.launch
```

### Keyboard Inputs  
`Quit (press "q"):` To end the ROI publisher, press "`q`" in the opened openCV window.  
`Night mode (press "n"):` If you don't want to see the video image on the opened openCV window, you can press "`n`" to turn on the night mode.  
`Show boxes (press "b"):` If you don't want to see the selected ROI on the opened openCV window, you can press "`b`" to toggle the showing boxes.  
`Show text (press "t"):` If you don't want to see the information texts on the opened openCV window, you can press "`t`" to toggle the showing text.

### Note: If you have a ROS bag file, you can play it in loop with this command:
```
rosbag play -l <name of your rosbag file>.bag
```
for example we have provided in this repo a test file in `/test` directory which includes image stream from topic `ir/image_raw`. It is a ~5 FPS video. To run it:
```
rosbag play -l test_1.bag
```