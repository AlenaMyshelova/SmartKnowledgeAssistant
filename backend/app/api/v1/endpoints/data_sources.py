from fastapi import APIRouter, HTTPException
from app.services.data_service import data_service

router = APIRouter()

@router.get("/data-sources")
def get_data_sources():
    try:
        return data_service.get_all_data_sources()
    except Exception as e:
        print(f"Error getting data sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get data sources")

@router.get("/categories") 
def get_categories():
    try:
        categories = data_service.get_categories()
        return {"categories": categories}
    except Exception as e:
        print(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to get categories")

@router.get("/faqs/{category}")
def get_faqs_by_category(category: str):
    try:
        faqs = data_service.get_faqs_by_category(category)
        return {"faqs": faqs, "category": category}
    except Exception as e:
        print(f"Error getting FAQs for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get FAQs for category: {category}")

@router.get("/statistics")
def get_data_statistics():
    try:
        stats = data_service.get_data_statistics()
        return stats
    except Exception as e:
        print(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")