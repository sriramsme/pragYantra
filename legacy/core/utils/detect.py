import cv2
import tensorflow as tf
# from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import easyocr
from .. import MODELS_DIR

def detect_faces(image_path):
    # Load the pre-trained face detection model from OpenCV
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Read the image
    image = cv2.imread(image_path)
    
    # Convert the image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect faces in the image
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    # Draw rectangles around the faces
    for (x, y, w, h) in faces:
        cv2.rectangle(image, (x, y), (x+w, y+h), (255, 0, 0), 2)

    # Save the image
    cv2.imwrite('detected_faces.png', image)

    return faces

def detect_objects(image_path):
    # Load the pre-trained object detection model from TensorFlow
    detection_model = tf.saved_model.load('path/to/saved_model')
    
    # Read the image
    image = cv2.imread(image_path)
    
    # Preprocess the image
    resized_image = cv2.resize(image, (300, 300))
    input_tensor = tf.convert_to_tensor(resized_image)
    input_tensor = input_tensor[tf.newaxis, ...]
    
    # Perform object detection
    detections = detection_model(input_tensor)
    
    return detections

def detect_text(image_path):
    
    reader = easyocr.Reader(['en'],gpu=False) # this needs to run only once to load the model into memory
    result = reader.readtext(image_path)
    
    return result

def extract_text(image_path):
    reader = easyocr.Reader(['en'],gpu=False) # this needs to run only once to load the model into memory
    result = reader.readtext(image_path, detail=0)
    
    return result

# def extract_text_handwritten(image_path):
    
#     # Load the processor and model from a specific folder
#     processor = TrOCRProcessor.from_pretrained(os.path.join(MODELS_DIR,'trOCR')
#     model = VisionEncoderDecoderModel.from_pretrained(os.path.join(MODELS_DIR,'trOCR')

#     image = Image.open(image_path).convert("RGB")

#     pixel_values = processor(image, return_tensors="pt").pixel_values
#     generated_ids = model.generate(pixel_values)

#     generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
#     return generated_text

import time

if __name__ == '__main__':
    image_path="example.jpg"

    # Test the face detection function
    start_time = time.time()
    faces = detect_faces(image_path)
    end_time = time.time()
    verbose_print(f"Face detection took {end_time - start_time} seconds")
    verbose_print(faces)
    
    verbose_print("\n\n====================\n\n")
    # Test the object detection function
    # start_time = time.time()
    # detections = detect_objects(image_path)
    # end_time = time.time()
    # verbose_print(f"Object detection took {end_time - start_time} seconds")
    # verbose_print(detections)
    
    # Test the text detection function
    start_time = time.time()
    text = detect_text(image_path)
    end_time = time.time()
    verbose_print(f"Text detection took {end_time - start_time} seconds")
    verbose_print(text)
    verbose_print("\n\n====================\n\n")
    # Test the text extraction function
    start_time = time.time()
    extracted_text = extract_text(image_path)
    end_time = time.time()
    verbose_print(f"Text extraction took {end_time - start_time} seconds")
    verbose_print(extracted_text)
    verbose_print("\n\n====================\n\n")
    # Test the handwritten text extraction function
    # start_time = time.time()
    # extracted_handwritten_text = extract_text_handwritten(image_path)
    # end_time = time.time()
    # verbose_print(f"Handwritten text extraction took {end_time - start_time} seconds")
    # verbose_print(extracted_handwritten_text)
    # verbose_print("\n\n====================\n\n")