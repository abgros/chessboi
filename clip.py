import cv2
import numpy as np

class GameClip:
	def __init__(self, width, height, fps, clip_name):
		# I can't find a working codec
		# self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
		
		# use -1 and it magically finds a working codec
		self.clip = cv2.VideoWriter(clip_name, -1, fps, (width, height))
	
	def add_img(self, PIL_img, frames=1):
		for i in range(frames):
			self.clip.write(cv2.cvtColor(np.array(PIL_img), cv2.COLOR_RGB2BGR))
	
	def save(self):
		self.clip.release()