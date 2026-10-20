# PragYantra

PragYantra is a simple software project designed to simulate a humanoid robot with vision, hearing, speech, and memory functionalities. This project aims to create a flexible platform for experimenting with artificial intelligence and human-machine interaction. As of now, it is more like an LLM, but with extended capabilities, enabling it to see, hear and engage in verbal communication.

![PragYantra's Architecture](arch.jpg)

## Features

- **Vision**: PragYantra simulates vision capabilities, allowing it to process live image captions. While it currently doesn't make decisions based on visual data, this feature lays the foundation for future development in this area.
- **Hearing**: PragYantra can perceive sounds and respond in realtime accordingly.
- **Speech**: Capable of generating simulated speech output and communicate with users in natural language.
- **Memory**: It has very limited memory capabilities, allowing it to store and recall information from recent interactions. Currently, I'm working on integrating a vector database to enhance the memory feature, providing more human-like memory capabilities, like short-term and long-term memories, enabling it to simulate complex recall tasks.

## Technical details

I prioritized PragYantra to have offline capabilities while also integrating online functionalities. To achieve this, all components of the project were designed to have offline capabilities, with online functionalities available as optional features. While using offline mode may require a stronger device for faster inference, the project is fully functional and performs admirably under these conditions.

The backbone of PragYantra consists of various open-source models for tasks such as text-to-speech, speech-to-text, text-to-text, and image-to-text conversion. These models serve as the building blocks upon which PragYantra's architecture is built, with additional capabilities and concurrency seamlessly integrated to enhance overall performance and user experience.

## So...what does PragYantra mean?

PragYantra, derived from Sanskrit, is a fusion of two words: "Prag" meaning intelligent or wise, and "Yantra" referring to machine or robot. So, put together, PragYantra embodies the concept of an intelligent machine, reflecting the project's goal of creating a flexible platform for experimenting with AI and human-machine interaction.

## Setup and Installation

To set up the project, follow these steps:

1. Clone the repository:

   ```
   git clone https://github.com/sri0606/pragyantra.git
   ```

2. Navigate to the project directory:

   ```
   cd pragyantra
   ```

3. Run the setup script:

   - Run the python setup script:
     ```
     python setup.py
     ```

   OR

   - On Unix-like systems (like Linux or macOS):
     ```
     chmod +x setup.sh
     ./setup.sh
     ```
   - On Windows, using Git Bash:
     ```
     bash setup.sh
     ```

The setup script will install the dependencies, download the required models, and create the necessary directories.

## Run the program and interact

For help, run the following command:

```
python main.py --help
```

Example commands:

- Offline mode

  ```bash
  python main.py --interpreter_model llama3_8B --offline_mode --speaker_model pyttsx3
  ```

- Online mode

  ```bash
  python main.py --interpreter_model llama3-70B-8192 --speaker_model pyttsx3

  or

  python main.py --interpreter_model mixtral-8x7b-32768 --speaker_model 11labs
  ```

## Citations and Acknowledgements

```bitbtex
@misc {nlp_connect_2022,
   author = { {NLP Connect} },
   title = { vit-gpt2-image-captioning (Revision 0e334c7) },
   year = 2022,
   url = { https://huggingface.co/nlpconnect/vit-gpt2-image-captioning },
   doi = { 10.57967/hf/0222 },
   publisher = { Hugging Face }
   }

@article{pratap2023mms,
   title={Scaling Speech Technology to 1,000+ Languages},
   author={Vineel Pratap and Andros Tjandra and Bowen Shi and Paden Tomasello and Arun Babu and Sayani Kundu and Ali Elkahky and Zhaoheng Ni and Apoorv Vyas and Maryam Fazel-Zarandi and Alexei Baevski and Yossi Adi and Xiaohui Zhang and Wei-Ning Hsu and Alexis Conneau and Michael Auli},
   journal={arXiv},
   year={2023}
   }

@misc{li2021trocr,
   title={TrOCR: Transformer-based Optical Character Recognition with Pre-trained Models},
   author={Minghao Li and Tengchao Lv and Lei Cui and Yijuan Lu and Dinei Florencio and Cha Zhang and Zhoujun Li and Furu Wei},
   year={2021},
   eprint={2109.10282},
   archivePrefix={arXiv},
   primaryClass={cs.CL}
   }
```
