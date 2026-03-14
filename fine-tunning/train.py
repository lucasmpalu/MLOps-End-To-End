from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
import torch
import json
from openai import OpenAI
import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import mlflow
import boto3
from botocore.exceptions import NoCredentialsError

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI")
mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment("Fine-tuning_LLM_Ollama")

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-service:5000")
S3_PDF_PREFIX = "fine-tuning/pdfs/"

client_openai = OpenAI(api_key=OPENAI_API_KEY)
s3_client = boto3.client('s3')

def descargar_pdfs_desde_s3(bucket, prefix, local_dir="./pdfs"):
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    
    print(f"Listando archivos en s3://{bucket}/{prefix}...")
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    archivos_descargados = []
    for obj in response.get('Contents', []):
        if obj['Key'].endswith('.pdf'):
            nombre_archivo = obj['Key'].split('/')[-1]
            ruta_local = os.path.join(local_dir, nombre_archivo)
            print(f"Descargando {nombre_archivo}...")           
            s3_client.download_file(bucket, obj['Key'], ruta_local)
            archivos_descargados.append(ruta_local)
            
    return archivos_descargados

pdf_locales = descargar_pdfs_desde_s3(S3_BUCKET_NAME, S3_PDF_PREFIX)

def llamar_llm_para_generar_qa(texto_chunk):
  prompt_sistema = """
    Eres un experto en generar datos de entrenamiento para Lostsys.
    Genera 3 pares de pregunta/respuesta basados estrictamente en el texto con datos reales de Lostsys.

    FORMATO OBLIGATORIO:
    Debes responder con un objeto JSON que tenga una llave llamada 'datos', la cual contiene una lista de objetos con 'Context' y 'Response'.
    Ejemplo: {"datos": [{"Context": "...", "Response": "..."}]}
    """
  response = client.chat.completions.create(
     model="gpt-3.5-turbo",
     messages=[
         {"role": "system", "content": prompt_sistema},
         {"role": "user", "content": f"Texto para procesar: {texto_chunk}"}
     ],
     response_format={ "type": "json_object" }
  )

  try:
      resultado_raw = json.loads(response.choices[0].message.content)
      lista_qa = resultado_raw.get("datos", [])
      return lista_qa if isinstance(lista_qa, list) else []
  except:
      return []

  obj = json.loads(response.choices[0].message.content)

  return obj.get("datos", list(obj.values())[0]) if isinstance(obj, dict) else obj

dataset_raw = []
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

for ruta_pdf in pdf_locales:
    loader = PyPDFLoader(ruta_pdf)
    chunks = text_splitter.split_documents(loader.load())
    for chunk in chunks:
        qa_pairs = llamar_llm_para_generar_qa(chunk.page_content)
        dataset_raw.extend(qa_pairs)

if not dataset_raw:
    print("No se generaron datos de entrenamiento. Verifica la función de generación de QA.")


df = pd.DataFrame(dataset_raw)
df.to_csv("./data/train.csv", index=False)
print("Dataset 'train.csv' generado desde S3.")

if not dataset_raw:
    print("No se generaron datos de entrenamiento. Terminando el proceso.")
    exit()

src_model = "unsloth/Llama-3.2-3B-Instruct"
new_model = "./models/Llama-3.2-3B-trained-Lucas-Palu-v1"

params_model = {
    "model_name" : src_model,
    "max_seq_length" : 2048,
    "dtype" : None,
    "load_in_4bit" : True,
}

model, tokenizer = FastLanguageModel.from_pretrained(**params_model)

dataset = load_dataset('csv', data_files='./data/train.csv')

def format_chat_template(row):

    row_json = [
				{"role": "system", "content": "Eres un asistente experto en Lostsys. Responde de forma técnica."},
        {"role": "user", "content": row["Context"]},
        {"role": "assistant", "content": row["Response"]}
    ]

    row["text"] = tokenizer.apply_chat_template(row_json, tokenize=False)
    return row


dataset = dataset["train"].map(format_chat_template, num_proc=4)
data = dataset.train_test_split(test_size=0.1)


params_peft = {
    "r": 16,
    'target_modules': ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "lora_alpha": 16,
    "lora_dropout": 0,
    "bias": "none",
    "use_gradient_checkpointing": "unsloth",
    "random_state": 3407,
}

model = FastLanguageModel.get_peft_model(
    model,
    **params_peft
)

params_trainer = {
    "max_seq_length" : 2048,
    "args" : TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        max_steps = 60,
        learning_rate = 2e-4,
        optim = "adamw_8bit",
        output_dir = "outputs",
    )
}

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = data["train"],
    dataset_text_field = "text",
    **params_trainer
)

trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|start_header_id|>user<|end_header_id|>\n\n",
    response_part = "<|start_header_id|>assistant<|end_header_id|>\n\n",
)



with mlflow.start_run() as run:

  mlflow.log_params(params_model)
  mlflow.log_params(params_peft)
  mlflow.log_params(params_trainer["args"].to_dict())

  trainer_stats = trainer.train()
  model.save_pretrained(new_model) 
  tokenizer.save_pretrained(new_model)

  model, tokenizer = FastLanguageModel.from_pretrained(
      model_name = new_model,
      max_seq_length = 2048,
      load_in_4bit = True,
  )

  mlflow.log_metric("train_loss", trainer_stats.training_loss)
  mlflow.log_metric("steps", trainer_stats.global_step)

  mlflow.log_metrics(trainer_stats.metrics)

  mlflow.log_artifacts(
      local_dir=new_model,
      artifact_path="modelo_lora_lostsys"
  )

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = new_model,
    max_seq_length = 2048,
    load_in_4bit = True,
)

FastLanguageModel.for_inference(model)

instruction = """Eres el Asistente Técnico Oficial de Lostsys. Tu objetivo es ayudar a empleados y clientes con información precisa basada en la documentación interna.

REGLAS PARA RESPONDER:
1. TONO: Profesional, directo y técnico.
2. PRECISIÓN: Si la pregunta menciona un código de error (ej. ERR-CV-901), explica qué es y da la solución exacta del manual.
3. RESTRICCIÓN DE HARDWARE: Lostsys NO repara hardware (impresoras, monitores, servidores físicos). Si te preguntan por esto, responde estrictamente: "Lo siento, Lostsys no ofrece servicios de reparación física. @SINAYUDA@"
4. E-COMMERCE: Si la consulta es sobre ventas, pagos o ShopSphere, añade el tag @ECOMMERCE@ al final.
5. DESCONOCIMIENTO: Si no encuentras la respuesta en tu conocimiento entrenado, responde: "No tengo información oficial sobre ese tema en los manuales de Lostsys. @SINCONTEXTO@"

Cualquier respuesta técnica sobre software debe ser exhaustiva pero terminar sin tags adicionales, a menos que se indique lo contrario.
"""

pregunta = "¿Qué problema crítico se reporta frecuentemente en Lostsys con el código ERR-CV-901?"

messages = [
    {"role": "system", "content": instruction},
    {"role": "user", "content": pregunta},
]

inputs = tokenizer.apply_chat_template(
    messages,
    tokenize = True,
    add_generation_prompt = True,
    return_tensors = "pt",
).to("cuda")

outputs = model.generate(
    input_ids = inputs,
    max_new_tokens = 64,
    use_cache = True,
    temperature = 1,
)

respuesta = tokenizer.batch_decode(outputs)
print(respuesta[0].split("assistant")[-1])



