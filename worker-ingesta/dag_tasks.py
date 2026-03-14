import os
import boto3
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector 
from langchain_text_splitters import RecursiveCharacterTextSplitter
from botocore.exceptions import ClientError

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "lostsys-mlops-data-lucas-palu")
S3_PREFIX_NUEVOS = "ingesta/nuevos_pdfs/"
S3_PREFIX_PROCESADOS = "ingesta/pdfs_procesados/"
CONNECTION_STRING = os.getenv("DATABASE_URL")

s3_client = boto3.client()

def check_new_pdfs_s3():

    nuevos = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=S3_PREFIX_NUEVOS)
    all_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.pdf')]
    
    if not nuevos:
        print("No hay nada nuevo.")
        return []

    resultado = ",".join(nuevos)
    print(f"Encontrados {len(nuevos)} archivos nuevos.")
    return resultado


def extract_and_load_s3(index, **kwargs): 

    if nuevos_files is None:
        ti = kwargs.get('ti')
        if ti:
            raw_xcom = ti.xcom_pull(task_ids='identificar_nuevos_pdf')
            nuevos_files = [f.strip() for f in raw_xcom.split(",") if f.strip()]

    if not nuevos_files:
        print("Finalizado: Nada nuevo que procesar.")
        return

    documents = []
    for s3_key in nuevos_files:
        pdf_name = s3_key.split('/')[-1]
        local_path = f"/tmp/{pdf_name}"-
        print(f"Descargando {pdf_name}...")
        s3_client.download_file(S3_BUCKET_NAME, s3_key, local_path)
        loader = PyMuPDFLoader(local_path)
        documents.extend(loader.load())

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=150) 
    chunks = text_splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings(model='text-embedding-3-small') 
        
    vector_store = PGVector.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=index,
            connection=CONNECTION_STRING
        )

    print("Moviendo archivos procesados a su nueva carpeta en S3...")
    for s3_key in nuevos_files:
        pdf_name = s3_key.split('/')[-1]
        new_key = f"{S3_PREFIX_PROCESADOS}{pdf_name}"

        copy_source = {'Bucket': S3_BUCKET_NAME, 'Key': s3_key}
        s3_client.copy_object(CopySource=copy_source, Bucket=S3_BUCKET_NAME, Key=new_key)

        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        print(f" - Movido con éxito: {new_key}")

    print("DAG finalizado. Vectores en RDS y archivos organizados en S3.")


if __name__ == "__main__":
    archivos = os.getenv("ARCHIVOS_NUEVOS") 
    indice = os.getenv("INDEX_NAME")
    
    if archivos:
        lista_archivos = archivos.split(",")
        extract_and_load_s3(index=indice, files=lista_archivos)
    else:
        print("No se recibieron archivos para procesar.")