import logging
from fastapi import APIRouter, HTTPException, status

from app.services.data_service import data_service

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["data-sources"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Service error"},
    },
)

@router.get("/data-sources")
def get_data_sources():
    try:
        return data_service.get_all_data_sources()
    except Exception as e:
        logger.error(f"Error getting data sources: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get data sources")


@router.get("/categories")
def get_categories():
    try:
        categories = data_service.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get categories")


@router.get("/faqs/{category}")
def get_faqs_by_category(category: str):
    try:
        faqs = data_service.get_faqs_by_category(category)
        return {"faqs": faqs, "category": category}
    except Exception as e:
        logger.error(f"Error getting FAQs for category {category}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get FAQs for category: {category}")


@router.get("/statistics")
def get_data_statistics():
    try:
        stats = data_service.get_data_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get statistics")