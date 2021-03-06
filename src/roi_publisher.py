#!/usr/bin/env python

""" 
    A modified version of https://github.com/pirobot/ros-by-example/blob/master/rbx_vol_1/rbx1_vision/src/ros2opencv2.py
"""

import rospy
import cv2 as cv2
import sys
from sensor_msgs.msg import Image, RegionOfInterest
from cv_bridge import CvBridge, CvBridgeError
import time
import numpy as np

class ROS2OpenCV2_ROI(object):
    def __init__(self, node_name):        
        self.node_name = node_name

        rospy.init_node(node_name)
        rospy.loginfo("Starting node " + str(node_name))

        rospy.on_shutdown(self.cleanup)
        
        # A number of parameters to determine what gets displayed on the
        # screen. These can be overridden the appropriate launch file
        self.input_rgb_image_topic_name = rospy.get_param("~input_rgb_image_topic_name")
        self.output_roi_topic_name = rospy.get_param("~output_roi_topic_name", 'roi')

        self.show_text = rospy.get_param("~show_text", True)
        self.show_boxes = rospy.get_param("~show_boxes", True)
        self.feature_size = rospy.get_param("~feature_size", False)

        # Initialize the Region of Interest and its publisher
        self.ROI = RegionOfInterest()
        self.roi_pub = rospy.Publisher(self.output_roi_topic_name, RegionOfInterest, queue_size = 1)
        
        # Initialize a number of global variables
        self.frame = None
        self.frame_size = None
        self.frame_width = None
        self.frame_height = None
        self.marker_image = None
        self.display_image = None
        self.grey = None
        self.prev_grey = None
        self.selected_point = None
        self.selection = None
        self.drag_start = None
        self.keystroke = None
        self.detect_box = None
        self.keep_marker_history = False
        self.night_mode = False
        self.cps = 0 # Cycles per second = number of processing loops per second.
        self.cps_values = list()
        self.cps_n_values = 20
        self.resize_window_width = 0
        self.resize_window_height = 0
        
        # Create the main display window
        self.cv_window_name = self.node_name
        
        # Create the cv_bridge object
        self.bridge = CvBridge()

        # Subscribe to the image topics and set the appropriate callbacks
        # The image topic names can be remapped in the appropriate launch file
        self.image_sub = rospy.Subscriber(self.input_rgb_image_topic_name, Image, self.image_callback)
                                    
    def on_mouse_click(self, event, x, y, flags, param):
        # This function allows the user to selection a ROI using the mouse
        if self.frame is None:
            return
        
        if event == cv2.EVENT_LBUTTONDOWN and not self.drag_start:
            self.features = []
            self.detect_box = None
            self.selected_point = (x, y)
            self.drag_start = (x, y)
            
        if event == cv2.EVENT_LBUTTONUP:
            self.drag_start = None
            self.classifier_initialized = False
            self.detect_box = self.selection
            
        if self.drag_start:
            xmin = max(0, min(x, self.drag_start[0]))
            ymin = max(0, min(y, self.drag_start[1]))
            xmax = min(self.frame_width, max(x, self.drag_start[0]))
            ymax = min(self.frame_height, max(y, self.drag_start[1]))
            self.selection = (xmin, ymin, xmax - xmin, ymax - ymin)
            
    def image_callback(self, data):

        cv2.namedWindow(self.cv_window_name, cv2.WINDOW_NORMAL)
        # Set a call back on mouse clicks on the image window
        cv2.setMouseCallback (self.node_name, self.on_mouse_click, None)
        if self.resize_window_height > 0 and self.resize_window_width > 0:
            cv2.resizeWindow(self.cv_window_name, self.resize_window_width, self.resize_window_height)
        else:
            cv2.resizeWindow(self.cv_window_name, 640, 480)

        # Store the image header in a global variable
        self.image_header = data.header

        # Time this loop to get cycles per second
        start = time.time()
        
        # Convert the ROS image to OpenCV format using a cv_bridge helper function
        frame = self.convert_image(data)
        
        # Store the frame width and height in a pair of global variables
        if self.frame_width is None:
            self.frame_size = (frame.shape[1], frame.shape[0])
            self.frame_width, self.frame_height = self.frame_size            
            
        # Create the marker image we will use for display purposes
        if self.marker_image is None:
            self.marker_image = np.zeros_like(frame)
            
        # Copy the current frame to the global image in case we need it elsewhere
        self.frame = frame.copy()

        # Reset the marker image if we're not displaying the history
        if not self.keep_marker_history:
            self.marker_image = np.zeros_like(self.marker_image)
        
        # Process the image to detect and track objects or features
        processed_image = self.process_image(frame)
        
        # If the result is a greyscale image, convert to 3-channel for display purposes """
        #if processed_image.channels == 1:
            #cv2.CvtColor(processed_image, self.processed_image, cv2.CV_GRAY2BGR)
        #else:
        
        # Make a global copy
        self.processed_image = processed_image.copy()
        
        # Display the user-selection rectangle or point 
        self.display_selection()
        
        # Night mode: only display the markers
        if self.night_mode:
            self.processed_image = np.zeros_like(self.processed_image)
            
        # Merge the processed image and the marker image
        self.display_image = cv2.bitwise_or(self.processed_image, self.marker_image)

        # If we have a detect box, then display it.  The detect box is a regular cvRect (x,y,w,h) 
        if self.show_boxes:
            # display the detect box if present
            if self.detect_box is not None and self.is_rect_nonzero(self.detect_box):
                (pt1_x, pt1_y, w, h) = self.detect_box
                cv2.rectangle(self.display_image, (pt1_x, pt1_y), (pt1_x + w, pt1_y + h), (50, 255, 50), self.feature_size, 8, 0)
        
        # Publish the ROI
        self.publish_roi()
        
        # Handle keyboard events
        self.keystroke = cv2.waitKey(5)
            
        # Compute the time for this loop and estimate CPS as a running average
        end = time.time()
        duration = end - start
        fps = int(1.0 / duration)
        self.cps_values.append(fps)
        if len(self.cps_values) > self.cps_n_values:
            self.cps_values.pop(0)
        self.cps = int(sum(self.cps_values) / len(self.cps_values))
        
        # Display CPS and image resolution if asked to
        if self.show_text:
            font_face = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5

            """ Print cycles per second (CPS) and resolution (RES) at top of the image """
            if self.frame_size[0] >= 640:
                vstart = 25
                voffset = int(50 + self.frame_size[1] / 120.)
            elif self.frame_size[0] == 320:
                vstart = 15
                voffset = int(35 + self.frame_size[1] / 120.)
            else:
                vstart = 10
                voffset = int(20 + self.frame_size[1] / 120.)
            cv2.putText(self.display_image, "CPS: " + str(self.cps), (10, vstart), font_face, font_scale, (255, 255, 0))
            cv2.putText(self.display_image, "RES: " + str(self.frame_size[0]) + "X" + str(self.frame_size[1]), (10, voffset), font_face, font_scale, (255, 255, 0))
       
	#print("Show image")
        # Update the image display
        cv2.imshow(self.node_name, self.display_image)
        
        # Process any keyboard commands
        if 32 <= self.keystroke and self.keystroke < 128:
            cc = chr(self.keystroke).lower()
            if cc == 'n':
                self.night_mode = not self.night_mode
            elif cc == 'b':
                self.show_boxes = not self.show_boxes
            elif cc == 't':
                self.show_text = not self.show_text
            elif cc == 'q':
                # The has press the q key, so exit
                rospy.signal_shutdown("User hit q key to quit.")
                
          
    def convert_image(self, ros_image):
        # Use cv_bridge() to convert the ROS image to OpenCV format
        try:
            cv_image = self.bridge.imgmsg_to_cv2(ros_image, "bgr8")       
            return np.array(cv_image, dtype=np.uint8)
        except CvBridgeError as e:
            print(e)
          

            
    def publish_roi(self):
        if not self.drag_start:
            if self.detect_box is not None:
                roi_box = self.detect_box
            else:
                return
        try:
            roi_box = self.cvBox2D_to_cvRect(roi_box)
        except:
            return
        
        # Watch out for negative offsets
        roi_box[0] = max(0, roi_box[0])
        roi_box[1] = max(0, roi_box[1])
        
        try:
            ROI = RegionOfInterest()
            ROI.x_offset = int(roi_box[0])
            ROI.y_offset = int(roi_box[1])
            ROI.width = int(roi_box[2])
            ROI.height = int(roi_box[3])
            self.roi_pub.publish(ROI)
        except:
            rospy.loginfo("Publishing ROI failed")
          
    def process_image(self, frame): 
        return frame
    
    
    def display_selection(self):
        # If the user is selecting a region with the mouse, display the corresponding rectangle for feedback.
        if self.drag_start and self.is_rect_nonzero(self.selection):
            x,y,w,h = self.selection
            cv2.rectangle(self.marker_image, (x, y), (x + w, y + h), (0, 255, 255), self.feature_size)
            self.selected_point = None

        # Else if the user has clicked on a point on the image, display it as a small circle.            
        elif not self.selected_point is None:
            x = self.selected_point[0]
            y = self.selected_point[1]
            cv2.circle(self.marker_image, (x, y), self.feature_size, (0, 255, 255), self.feature_size)
        
    def is_rect_nonzero(self, rect):
        # First assume a simple CvRect type
        try:
            (_,_,w,h) = rect
            return (w > 0) and (h > 0)
        except:
            try:
                # Otherwise, assume a CvBox2D type
                ((_,_),(w,h),a) = rect
                return (w > 0) and (h > 0)
            except:
                return False
        
    def cvBox2D_to_cvRect(self, roi):
        try:
            if len(roi) == 3:
                (center, size, angle) = roi
                pt1 = (int(center[0] - size[0] / 2), int(center[1] - size[1] / 2))
                pt2 = (int(center[0] + size[0] / 2), int(center[1] + size[1] / 2))
                rect = [pt1[0], pt1[1], pt2[0] - pt1[0], pt2[1] - pt1[1]]
            else:
                rect = list(roi)
        except:
            return [0, 0, 0, 0]
            
        return rect
        
    def cvRect_to_cvBox2D(self, roi):
        try:
            if len(roi) == 3:
                box2d = roi
            else:
                (p1_x, p1_y, width, height) = roi
                center = (int(p1_x + width / 2), int(p1_y + height / 2))
                size = (width, height)
                angle = 0
                box2d = (center, size, angle)
        except:
            return None
            
        return list(box2d)
        
    def cleanup(self):
        print ("Shutting down roi_publisher node.")
        cv2.destroyAllWindows()       

def main(args):    
    try:
        node_name = "roi_publisher"
        ROS2OpenCV2_ROI(node_name)
        rospy.spin()
    except KeyboardInterrupt:
        print ("Shutting down roi_publisher node.")
        cv2.DestroyAllWindows()

if __name__ == '__main__':
    main(sys.argv)
