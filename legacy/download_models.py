from transformers import VitsModel, VitsTokenizer,VisionEncoderDecoderModel,ViTImageProcessor, AutoTokenizer,TrOCRProcessor,BertTokenizer, BertModel
import os
import requests

# from https://fgiasson.com/blog/index.php/2023/08/23/how-to-deploy-hugging-face-models-in-a-docker-container/

def download_models(model_path):
    """Download a Hugging Face model and tokenizer to the specified directory"""
    print("Downloading all the models used in PragYantra to given directory...")
    # Check if the directory already exists
    if not os.path.exists(model_path):
        # Create the directory
        os.makedirs(model_path)
    
    #install Vits model for facebokk-mms
    model = VitsModel.from_pretrained("facebook/mms-tts-eng")
    tokenizer = VitsTokenizer.from_pretrained("facebook/mms-tts-eng")
    model.save_pretrained(model_path+"facebook_mms_tts_eng")
    tokenizer.save_pretrained(model_path+"facebook_mms_tts_eng")

    #install gpt-image-captioning
    model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    feature_extractor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    model.save_pretrained(model_path+"gpt2-image-captioning")
    feature_extractor.save_pretrained(model_path+"gpt2-image-captioning")
    tokenizer.save_pretrained(model_path+"gpt2-image-captioning")

    #install microsoft-trOCR model
    processor = TrOCRProcessor.from_pretrained('microsoft/trocr-base-handwritten')
    model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-handwritten')
    processor.save_pretrained(model_path+"trOCR")
    model.save_pretrained(model_path+"trOCR")

    #install BERT
    model = BertModel.from_pretrained('bert-base-uncased')
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    model.save_pretrained(model_path+"bert-base-uncased")
    tokenizer.save_pretrained(model_path+"bert-base-uncased")

    def download_file(url, local_filename):
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk) 

    #install whisper model
    whisper_model_url = "https://openaipublic.azureedge.net/main/whisper/models/25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead/base.en.pt"
    download_file(whisper_model_url,model_path+"base.en.pt")

# Download the models
if __name__ == "__main__":
    download_models("models/")