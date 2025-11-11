import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Consent-based Check-in API running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# Models for requests
class CreateChildRequest(BaseModel):
    name: str

class CheckinRequest(BaseModel):
    child_id: str
    lat: float
    lng: float
    accuracy: Optional[float] = None
    note: Optional[str] = None
    link: Optional[str] = None

@app.post("/child")
def create_child(payload: CreateChildRequest):
    """Create a child profile (with consent)"""
    try:
        from schemas import Child
        child = Child(name=payload.name)
        inserted_id = create_document("child", child)
        return {"id": inserted_id, "name": payload.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/child")
def list_children():
    try:
        children = get_documents("child")
        # Convert ObjectId to string if present
        for c in children:
            if "_id" in c:
                c["id"] = str(c.pop("_id"))
        return children
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/checkin")
def create_checkin(payload: CheckinRequest):
    """Child shares their current location and optional link/note"""
    try:
        # verify child exists
        from bson import ObjectId
        if not ObjectId.is_valid(payload.child_id):
            raise HTTPException(status_code=400, detail="Invalid child_id")
        child = db["child"].find_one({"_id": ObjectId(payload.child_id)})
        if not child:
            raise HTTPException(status_code=404, detail="Child not found")

        from schemas import Checkin
        checkin = Checkin(
            child_id=payload.child_id,
            lat=payload.lat,
            lng=payload.lng,
            accuracy=payload.accuracy,
            note=payload.note,
            link=payload.link,
        )
        inserted_id = create_document("checkin", checkin)
        return {"id": inserted_id, "status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/checkin/latest")
def latest_checkins(limit: int = 10, child_id: Optional[str] = None):
    try:
        query = {}
        if child_id:
            query["child_id"] = child_id
        items = db["checkin"].find(query).sort("created_at", -1).limit(limit)
        result = []
        for it in items:
            it["id"] = str(it.pop("_id"))
            result.append(it)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

