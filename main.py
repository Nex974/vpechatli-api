from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv  # type: ignore
from firebase import db  # <-- your Firestore setup
import os
from openai import OpenAI
from subscription import check_and_update_access  # import our access checker

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://vpechatli.tech"],  # adjust if frontend is hosted elsewhere
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerationRequest(BaseModel):
    job_text: str
    cv_text: str


@app.post("/adapt-cv")
async def adapt_cv(data: GenerationRequest, request: Request):
    email = request.headers.get("x-user-email")
    if not email:
        raise HTTPException(status_code=401, detail="Missing user email in headers")

    await check_and_update_access(email)

    prompt = f"""
Ти си интелигентен асистент, който помага на хора да адаптират своето CV спрямо конкретна обява за работа.

На база следната обява:
{data.job_text}

И автобиографията на кандидата:
{data.cv_text}

Адаптирай CV-то така, че да подчертае най-подходящите умения и опит за позицията, като запазиш естествен и професионален стил.
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1000,
        )
        adapted_cv = completion.choices[0].message.content
        return {"cv": adapted_cv.strip()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/generate")
async def generate_letter(data: GenerationRequest, request: Request):
    email = request.headers.get("x-user-email")
    if not email:
        raise HTTPException(status_code=401, detail="Missing user email in headers")

    await check_and_update_access(email)

    prompt = f"""
Ти си интелигентен асистент, който помага на хора да напишат мотивационно писмо за работа.

На база следната обява:
{data.job_text}

И автобиографията на кандидата:
{data.cv_text}

Генерирай пълно мотивационно писмо, без повторения, с естествено звучащо начало и край. Използвай ясен, приятелски тон и не използвай клишета.
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=800,
        )
        letter = completion.choices[0].message.content
        return {"letter": letter.strip()}
    except Exception as e:
        return {"error": str(e)}
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
