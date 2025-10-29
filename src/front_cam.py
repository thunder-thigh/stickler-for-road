#File Objectives:
#Read data from a specified device and stream (runtime argument)
#Generate 3 UNIX sockets:
#   A. ./front_feed_raw             [video feed for monitoring]
#   B. ./front_feed_processesed     [-/-]
#   C. ./front_cam_objects          [on memory JSON file for immediate objects on front]

#GOALS:
#1. Build prototype in python
#2. Rewrite in C/C++ for speed
#2. Run this program in a cgroup at (20~ CPU CAP for)

