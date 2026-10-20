import time
import cv2
from deepface import DeepFace
import os
from typing import List, Union
import numpy as np

# Set the environment variable
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

def detect_faces(image_input, offset=20) -> List[np.ndarray]:
    """
    Detect faces in an image or video frame using OpenCV

    Parameters:
        image_input (str or ndarray): The path to the image file or a video frame
        offset (int): The offset to be added to the detected face rectangle. The default is 20.
    """
    # Load the pre-trained face detection model from OpenCV
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Check the type of the input
    if isinstance(image_input, str):
        # If it's a string, treat it as a file path and read the image from the file
        image = cv2.imread(image_input)
    elif isinstance(image_input, np.ndarray):
        # If it's a numpy array, treat it as a video frame
        image = image_input
    else:
        raise TypeError('image_input must be either a file path (str) or a video frame (numpy.ndarray)')

    # Detect faces in the image
    faces = face_cascade.detectMultiScale(image, 1.1, 4)

    face_images = []  # List to store the face images

    for i, (x, y, w, h) in enumerate(faces):
        # Add the offset to the rectangle coordinates
        x_off, y_off, w_off, h_off = x - offset, y - offset, w + 2*offset, h + 2*offset

        # Make sure the coordinates are within the image boundaries
        x_off = max(0, x_off)
        y_off = max(0, y_off)
        w_off = min(image.shape[1] - x_off, w_off)
        h_off = min(image.shape[0] - y_off, h_off)

        cv2.rectangle(image, (x_off, y_off), (x_off + w_off, y_off + h_off), (255, 0, 0), 2)
        face_image = image[y_off:y_off + h_off, x_off:x_off + w_off]  # Slice the rectangle from the image
        face_images.append(face_image)  # Add the face image to the list

    return face_images

def face_caption(faces: List[Union[str, np.ndarray]], actions=["emotion"]):
    """
    Get a caption/description for the face using DeepFace

    Parameters:
    faces (list): A list of exact path to the images or numpy arrays in BGR format,
        or a base64 encoded image. If the source image contains multiple faces, the result will include information for each detected face.
    actions (list): The actions to be performed on the image: emotion, age, gender, race. The default is ["emotion"].
    """
    captions = []
    for face in faces:
        result = DeepFace.analyze(img_path=face, actions=actions, enforce_detection=False)
        captions.append(result)

    return captions

if __name__ == '__main__':
    start_time = time.time()
    faces = detect_faces("test2.png")

    result = face_caption(faces, actions=["emotion"])
    print("Time taken: ", time.time() - start_time)
    print(result)