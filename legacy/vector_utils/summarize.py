import nltk
from sentence_transformers import SentenceTransformer, util
from transformers import T5Tokenizer, T5ForConditionalGeneration

def summarize_text(model:SentenceTransformer, text, min_summary:float=0.1, max_summary:float=0.65, min_similarity:float=0.2):
    """
    Summarize text using SBERT sentence transformer

    Args:
    - model (SentenceTransformer): SBERT model
    - text (str): The input text to be summarized.
    - min_summary (float, optional): The minimum length of the generated summary. Defaults to 0.1.
    - max_summary (float, optional): The maximum length of the generated summary. Defaults to 0.65.
    - min_similarity (float, optional): The minimum similarity score between sentences. Defaults to 0.2.
    """
    nltk.download('punkt')
    # Split the document into sentences
    sentences = nltk.sent_tokenize(text)#text.split('. ')

    # Compute sentence embeddings
    sentence_embeddings = model.encode(sentences, convert_to_tensor=True)

    # Compute pairwise cosine similarity between sentence embeddings
    similarity_matrix = util.pytorch_cos_sim(sentence_embeddings, sentence_embeddings)

    # Sort sentences by similarity scores
    ranked_sentences = sorted(((similarity_matrix[i].mean().item(), sentence) for i, sentence in enumerate(sentences)), reverse=True)

    # Initialize summary as an empty list
    summary = []

    # Initialize total length of summary
    total_length = 0

    # Iterate over the ranked sentences
    for score, sentence in ranked_sentences:
        # Check if sentence meets the minimum similarity score
        if score < min_similarity:
            continue

        # Check if adding the sentence would exceed the maximum summary length
        if total_length + len(sentence) > len(text) * max_summary:
            break

        # Add the sentence to the summary
        summary.append(sentence)

        # Update the total length of the summary
        total_length += len(sentence)

    # If the total length of the summary is less than the minimum summary length,
    # add the highest ranked sentences until the minimum length is reached
    for score, sentence in ranked_sentences:
        if total_length >= len(text) * min_summary:
            break
        if sentence not in summary:
            summary.append(sentence)
            total_length += len(sentence)

    # Before joining the sentences in the summary, reorder them to their original order
    summary.sort(key=sentences.index)

    # Join the sentences in the summary
    summary = '. '.join(summary)
    return summary



class Summarizer:
    """
    Summarizer class using T5 model
    """

    def __init__(self, model="t5-base") -> None:
        self.model = T5ForConditionalGeneration.from_pretrained(model)
        self.tokenizer = T5Tokenizer.from_pretrained(model)
        return

    def tokenize_and_truncate(self, text, max_length):
        # Tokenize input text 
        inputs = self.tokenizer(text, return_tensors="pt", max_length=max_length, truncation=True)
        return inputs

    def chunk_text(self, text, max_length):

        chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        return chunks

    def __get_summarized_tokens(self, input_text, max_length, min_length, length_penalty, 
                              num_beams, max_input_length,no_repeat_ngram_size):
        """
        Get the tokens for the summarized of given input text.

        @max_length : The maximum length of the generated summary.
        @min_length : The minimum length of the generated summary.
        @length_penalty : Length penalty to encourage or discourage longer summaries.
        @num_beams : Number of beams to use in beam search during generation.
        @max_input_length: Maximum length for input text chunks.

        Returns
        - list: The tokens for the summarized text.
        """
        # Chunk the input text
        text_chunks = self.chunk_text(input_text, max_input_length)
       
        # Summarize each chunk
        summary_tokens = []
        for chunk in text_chunks:
            chunk = "summarize:\n"+chunk
            # Tokenize and truncate input chunk
            inputs = self.tokenize_and_truncate(chunk, max_input_length)

            # Generate summary for the chunk
            summary_ids = self.model.generate(**inputs,max_new_tokens=max_length, min_new_tokens=min_length, 
                                              length_penalty=length_penalty, num_beams=num_beams,
                                              no_repeat_ngram_size=no_repeat_ngram_size)

            summary_tokens.append(summary_ids)

        return summary_tokens

    def summarize(self,input_text,max_length=40, min_length=20, length_penalty=-1, num_beams=2, max_input_length=512,no_repeat_ngram_size=3):
        """
        Summarize the given input_text.

        Parameters:
        @input_text: The input text to be summarized.
        @max_length : The maximum length of the generated summary.
        @min_length : The minimum length of the generated summary.
        @length_penalty : Length penalty to encourage or discourage longer summaries.
        @num_beams : Number of beams to use in beam search during generation.
        @max_input_length: Maximum length for input text chunks.
        @no_repeat_ngram_size: Size of n-grams for which repetition is not allowed in the beam search.

        Returns:
        - str: summary as text
        """
        summary_tokens = self.__get_summarized_tokens(input_text, max_length, min_length, length_penalty, 
                                                      num_beams, max_input_length,no_repeat_ngram_size)
        summaries = []
        for summary_ids in summary_tokens:
            summary_text = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            summaries.append(summary_text)

        # merge all summaries
        final_summary = " ".join(summaries)
        return final_summary
    

    

import time
if __name__ == '__main__':
    model = SentenceTransformer("all-MiniLM-L6-v2")
    t5model = Summarizer()
    document = "Add your text here"

    start_time = time.time()
    summary = summarize_text(model, document)
    print(f"Time taken for sbert: {time.time() - start_time:.2f}s\n")

    start_time=time.time()
    summary1 = t5model.summarize(document)
    print(f"Time taken for T5: {time.time() - start_time:.2f}s\n")

    print(f"\nsbertSummary:\n{summary}\n\n")
    print(f"t5 summary:\n{summary1}\n")