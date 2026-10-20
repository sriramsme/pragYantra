import torch
from datetime import datetime
from typing import List
from vector_utils.vector_emb import VectorNode, VectorStore, ModelSource
from . import verbose_print

class MemoryNode(VectorNode):
    """
    Representation of a memory node.
    """
    def __init__(self, key: str | int, embedding: torch.Tensor, **kwargs):
        """
        Args:

            key (str): The timestamp key to associate with the vector. (timestamp YYmmddHHMM (minutes can either be 00 or 30 as memory is added every 30mins))
        """
        super().__init__(key, embedding, **kwargs)

    def __str__(self):
        summary = self.kwargs.get('summary', 'No summary')
        return f"MemoryNode: {self.format_timestamp(self.key)} - {summary}"

    def __repr__(self):
        summary = self.kwargs.get('summary', '')
        return f"MemoryNode('{self.key}', '{self.embedding}', '{summary}')"

    @staticmethod
    def format_timestamp(timestamp):
        return f"{timestamp[6:8]}/{timestamp[4:6]}/{timestamp[:4]} {timestamp[8:10]}:{timestamp[10:12]}"


class MemoryStore(VectorStore):
    """
    Memory store. Inherits from VectorStore.
    """
    def __init__(self, embedding_model="all-MiniLM-L6-v2",model_source = ModelSource.SBERT):
        """
        Args:
            embedding_model (str): The identifier of the embedding model to use. Defaults to "all-MiniLM-L6-v2".
            model_source (ModelSource, optional): The source of the embedding model. Defaults to ModelSource.SBERT.
        """
        super().__init__(embedding_model,model_source,node_type=MemoryNode)
        

    def __getitem__(self, key) -> MemoryNode | List[MemoryNode]:
        if isinstance(key, datetime):
            key = key.strftime("%Y%m%d%H%M")
        elif isinstance(key, int):
            key = str(key)

        if len(key) == 12:  # Full format
            return self.vector_nodes[key]
        else:
            summaries = []
            for timestamp_key, memory_node in self.vector_nodes.items():
                if timestamp_key.startswith(key):
                    summaries.append((memory_node))
            return summaries
    

    def add_vector(self, key, text, summary=None):
        """
        Adds a vector to the database.

        Args:
            key (str): The timestamp key to associate with the vector. (timestamp YYmmddHHMM (minutes can either be 00 or 30 as memory is added every 30mins))
            text (str): The text to vectorize and add to the database.
            summary (list, optional): The summary associated with the vector. Defaults to None.
        """
        preprocess_text = self.preprocess_text(text, threshold_length=100)
        vector_emb = self.vectorize_text(preprocess_text)
        self.vector_nodes[key] = MemoryNode(key=key, embedding=vector_emb, summary=summary)

    def pre_seed_memory(self, data: dict, save_path=None):
        """
        Pre-seed the memory with given data kind of like initial memory configuration. 

        Args:
            data (dict): A dictionary of key-value pairs to seed the memory with. The key is the timestamp in the format YYMMDDHHMM (with minutes set to either 00 or 30) and the value is a tuple of the summary and text.
            save_path (str, optional): The path to save the memory to. Defaults to None.
        """
        if not data or not isinstance(data, dict):
            raise ValueError("Data must be a non-empty dictionary.")

        for timestamp,(summary,text)  in data.items():
            self.add_vector(key=timestamp, text=text,summary=summary )
        if save_path:
            self.save(save_path)

    def query(self, text, date=None, date_type='day', k=5, days_threshold=2):
        """
        Query embeddings for similar vectors. 
        You can query a text with specific day, month or year. The 'date' parameter should be in the format 'YYYYMMDD' for day, 'YYYYMM' for month, and 'YYYY' for year.

        Args:
            text (str): The query text.
            date (str, optional): Specific date to query for. Defaults to None.
            date_type (str, optional): The type of date query ('day', 'month', or 'year'). Defaults to 'day'.
            k (int, optional): The number of most similar vectors to return. Defaults to 5.
            days_threshold (int, optional): The threshold for the date. Defaults to 2.
        """
        
        if date is not None:
            nearest_nodes = [node for timestamp_key, node in self.vector_nodes.items() 
                        if date is None or 
                        (date_type == 'day' and abs((datetime.strptime(timestamp_key, "%Y%m%d%H%M") - datetime.strptime(date, "%Y%m%d")).days) <= days_threshold) or 
                        (date_type == 'month' and datetime.strptime(timestamp_key, "%Y%m%d%H%M").month == datetime.strptime(date, "%Y%m").month) or 
                        (date_type == 'year' and datetime.strptime(timestamp_key, "%Y%m%d%H%M").year == int(date))]
        
        elif date is None or len(nearest_nodes)==0:
            verbose_print("No vectors found for the given date. Searching entire database....")
            nearest_nodes = None

        query_emb = self.vectorize_text(text)
        if nearest_nodes is not None:
            hits = self.embedding_model.semantic_search(query_emb, nearest_nodes, top_k=k)
        else:
            hits = self.embedding_model.semantic_search(query_emb,list(self.vector_nodes.values()), top_k=k)

        return hits
    

    
import time

if __name__ == '__main__':
    # db = MemoryStore(embedding_model="bert-base-uncased",model_source=ModelSource.HUGGINGFACE)
    db = MemoryStore(embedding_model="all-MiniLM-L6-v2",model_source=ModelSource.SBERT)
    #genereated with chatgpt
    random_initial_memory = {
        '202303261530': ('Family Vacation to Italy',
        'Exploring ancient ruins and indulging in delicious Italian cuisine, soaking in the rich history and vibrant culture of Italy.'),
        '202210252200': ('Hiking Mount Kilimanjaro',
        'Reaching the summit of Mount Kilimanjaro after days of challenging trekking, feeling a sense of accomplishment and awe at the breathtaking views.'),
        '202009210500': ('First Day of College',
        'Navigating the bustling campus with a mix of excitement and nervousness, eager to embark on this new academic journey.'),
        '202107141830': ('Volunteering at a Homeless Shelter',
        'Spending a day serving meals and interacting with residents at a homeless shelter, feeling humbled and grateful for the opportunity to make a difference.'),
        '192109081830': ('Road Trip Across America',
        'Embarking on a cross-country road trip with friends, discovering hidden gems and creating unforgettable memories along the way.'),
        '192305222200': ('High School Prom',
        'Dancing the night away with friends, feeling like royalty in my elegant gown and making memories that would last a lifetime.'),
        '182011261100': ('Attending a Music Festival',
        'Immersing myself in the electrifying atmosphere of a music festival, dancing to my favorite bands and connecting with fellow music lovers.'),
        '202209051830': ('Skydiving for the First Time',
        'Feeling an exhilarating rush of adrenaline as I leaped from the plane and soared through the sky, overcome with a sense of freedom and thrill.'),
        '202003050730': ('Watching the Northern Lights',
        'Gazing up at the mesmerizing display of colors dancing across the night sky, feeling humbled by the beauty and wonder of the natural world.'),
        '192008230430': ('Cooking a Homemade Meal with Family',
        'Gathering in the kitchen with loved ones, sharing laughter and stories as we prepared a delicious homemade meal together.'),
        '202002252230': ("Celebrating New Year's Eve in Times Square",
        'Counting down to midnight amidst the sea of revelers in Times Square, feeling a sense of unity and excitement as we welcomed the new year.'),
        '202005082200': ("Attending a Friend's Wedding",
        'Witnessing the love and joy between two dear friends as they exchanged vows, feeling honored to be part of their special day.'),
        '192101082100': ('Scuba Diving in the Great Barrier Reef',
        'Exploring the vibrant underwater world of the Great Barrier Reef, swimming alongside colorful fish and majestic coral formations.'),
        '202206102000': ('Completing a Marathon',
        'Crossing the finish line of a marathon after months of training and dedication, feeling a surge of pride and accomplishment.'),
        '202211161630': ('Planting a Garden',
        'Getting my hands dirty in the soil and watching with joy as my garden bloomed with colorful flowers and delicious fruits and vegetables.')
    }


    # verbose_print("Initial memory config")
    # start_time = time.time()
    # db.pre_seed_memory(data = random_initial_memory, save_path='memory.h5')
    # verbose_print('Adding time sb:', time.time() - start_time)

    # Load the vectors from files (if needed)
    db.load('memory.h5')

    # Example queries
    query_texts = [
        "Recall the experience of hiking Mount Kilimanjaro.",
        "Retrieve memory of scuba diving in the Great Barrier Reef.",
        "Music and songs",
        "Covid 19 pandemic",
    ]
    dates = [None,None,1820,2021]
    for i,query in enumerate(query_texts):

        start_time = time.time()
        results1 = db.query(query,date=dates[i],date_type='year', k=3)
        verbose_print('Query time:', time.time() - start_time, f". Results for '{query}':")
        for result in results1:
            verbose_print(result[1], result[0].summary)
        verbose_print("\n")