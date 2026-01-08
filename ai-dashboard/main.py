import os
import json
import requests
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ANALYZER_URL = os.getenv("ANALYZER_URL", "http://ai-analyzer:5000")
TICKETS_FILE = "/app/data/tickets.json"

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    email: Optional[str] = None

class TicketStatusUpdate(BaseModel):
    status: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return User(username=username)
    except JWTError:
        raise credentials_exception

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Simple mock auth
    if form_data.username == "admin" and form_data.password == "password":
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# API Endpoints
@app.get("/insights")
async def get_insights(current_user: User = Depends(get_current_user)):
    try:
        resp = requests.get(f"{ANALYZER_URL}/insights")
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
async def get_analytics(current_user: User = Depends(get_current_user)):
    try:
        resp = requests.get(f"{ANALYZER_URL}/analytics")
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tickets")
async def get_tickets(current_user: User = Depends(get_current_user)):
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, 'r') as f:
            tickets_dict = json.load(f)
            return list(tickets_dict.values())
    return []

@app.post("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, update: TicketStatusUpdate, current_user: User = Depends(get_current_user)):
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, 'r') as f:
            tickets = json.load(f)
        if ticket_id in tickets:
            tickets[ticket_id]["status"] = update.status
            tickets[ticket_id]["updated_at"] = int(datetime.utcnow().timestamp() * 1000000000)
            with open(TICKETS_FILE, 'w') as f:
                json.dump(tickets, f, indent=2)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="Ticket not found")

@app.post("/query")
async def query_ai(query_data: dict, current_user: User = Depends(get_current_user)):
    try:
        resp = requests.post(f"{ANALYZER_URL}/query", json=query_data, timeout=70)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from AI analyzer: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to AI analyzer: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve Frontend
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)