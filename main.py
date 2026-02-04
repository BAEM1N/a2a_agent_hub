"""Agent Hub - A2A Agent Registration and Discovery Platform."""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import AUTH_REQUIRED
from database import init_db, get_db
from models import User, Agent
from auth import (
    SESSION_COOKIE_NAME,
    verify_password,
    create_session,
    get_user_id_from_session,
    delete_session,
    get_user_by_username,
    get_user_by_id,
    create_user,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(title="Agent Hub", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Pydantic Models ---


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class AgentRegisterRequest(BaseModel):
    url: str


class AgentTestRequest(BaseModel):
    message: str
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    tavily_api_key: Optional[str] = None
    custom_headers: Optional[dict[str, str]] = None  # X- prefix 커스텀 헤더


class AgentResponse(BaseModel):
    id: int
    url: str
    name: Optional[str]
    description: Optional[str]
    version: Optional[str]
    skills: Optional[list]
    provider: Optional[str]
    documentation_url: Optional[str]
    registered_by: str
    registered_at: str
    is_healthy: bool


# --- Dependencies ---


# 인증 비활성화 시 사용할 더미 유저
class AnonymousUser:
    id = 0
    username = "anonymous"


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Get current authenticated user."""
    if not AUTH_REQUIRED:
        return AnonymousUser()
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = get_user_id_from_session(session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not AUTH_REQUIRED:
        return AnonymousUser()
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = get_user_id_from_session(session_id)
    if not user_id:
        return None
    return await get_user_by_id(db, user_id)


# --- Page Routes ---


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Main page - agent list."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Login page."""
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Register page."""
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/playground", response_class=HTMLResponse)
async def playground_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Agent Playground - Postman-like testing interface."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("playground.html", {"request": request, "user": user})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """User profile - API settings and custom headers."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


# --- Auth API ---


@app.post("/api/auth/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Login endpoint."""
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=400,
        )
    session_id = create_session(user.id)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return response


@app.post("/api/auth/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Register endpoint."""
    if len(username) < 3:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username must be at least 3 characters"},
            status_code=400,
        )
    if len(password) < 4:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Password must be at least 4 characters"},
            status_code=400,
        )

    existing = await get_user_by_username(db, username)
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already exists"},
            status_code=400,
        )

    user = await create_user(db, username, password)
    session_id = create_session(user.id)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    """Logout endpoint."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_session(session_id)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


# --- Settings API ---


class ApiConfigRequest(BaseModel):
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    tavily_api_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_base_url: Optional[str] = None
    custom_headers: Optional[dict[str, str]] = None  # User-defined custom headers


@app.get("/api/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user's saved API config."""
    return user.api_config or {}


@app.put("/api/settings")
async def save_settings(
    config: ApiConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save user's API config."""
    # Filter out None values
    api_config = {k: v for k, v in config.model_dump().items() if v}
    user.api_config = api_config
    await db.commit()
    return {"status": "ok", "saved": list(api_config.keys())}


# --- Agent API ---


@app.get("/api/agents")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentResponse]:
    """List all registered agents."""
    result = await db.execute(select(Agent).order_by(Agent.registered_at.desc()))
    agents = result.scalars().all()

    # Get usernames for all agents
    user_ids = {a.user_id for a in agents}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u.username for u in users_result.scalars().all()}

    return [
        AgentResponse(
            id=a.id,
            url=a.url,
            name=a.name,
            description=a.description,
            version=a.version,
            skills=a.skills if a.skills else [],
            provider=a.provider,
            documentation_url=a.documentation_url,
            registered_by=users_map.get(a.user_id, "Unknown"),
            registered_at=a.registered_at.isoformat(),
            is_healthy=a.is_healthy,
        )
        for a in agents
    ]


@app.post("/api/agents")
async def register_agent(
    req: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentResponse:
    """Register a new agent by URL."""
    url = req.url.rstrip("/")

    # Check if agent already exists
    existing = await db.execute(select(Agent).where(Agent.url == url))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent already registered")

    # Fetch AgentCard from /.well-known/agent.json
    agent_card_url = f"{url}/.well-known/agent.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(agent_card_url)
            resp.raise_for_status()
            card = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch agent card from {agent_card_url}: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent card response: {str(e)}",
        )

    # Extract skills as list of skill info
    skills = []
    if "skills" in card:
        for skill in card.get("skills", []):
            skills.append({
                "id": skill.get("id"),
                "name": skill.get("name"),
                "description": skill.get("description"),
            })

    # Create agent record
    agent = Agent(
        url=url,
        name=card.get("name"),
        description=card.get("description"),
        version=card.get("version"),
        skills=skills,
        provider=card.get("provider", {}).get("organization") if isinstance(card.get("provider"), dict) else card.get("provider"),
        documentation_url=card.get("documentationUrl"),
        user_id=user.id,
        is_healthy=True,
        last_health_check=datetime.utcnow(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        url=agent.url,
        name=agent.name,
        description=agent.description,
        version=agent.version,
        skills=agent.skills if agent.skills else [],
        provider=agent.provider,
        documentation_url=agent.documentation_url,
        registered_by=user.username,
        registered_at=agent.registered_at.isoformat(),
        is_healthy=agent.is_healthy,
    )


@app.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete an agent (owner only)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this agent")

    await db.delete(agent)
    await db.commit()
    return {"status": "deleted"}


@app.post("/api/agents/{agent_id}/test")
async def test_agent(
    agent_id: int,
    req: AgentTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test an agent by sending a message."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Send A2A message to agent
    try:
        import uuid
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build headers with optional API keys
            headers = {"Content-Type": "application/json"}
            if req.openai_api_key:
                headers["X-OpenAI-API-Key"] = req.openai_api_key
            if req.openai_base_url:
                headers["X-OpenAI-Base-URL"] = req.openai_base_url
            if req.openai_model:
                headers["X-OpenAI-Model"] = req.openai_model
            if req.tavily_api_key:
                headers["X-Tavily-API-Key"] = req.tavily_api_key
            # Add custom headers with X- prefix
            if req.custom_headers:
                for key, value in req.custom_headers.items():
                    header_key = key if key.lower().startswith("x-") else f"X-{key}"
                    headers[header_key] = value

            # A2A protocol: POST to agent URL with JSON-RPC style message
            message_id = str(uuid.uuid4())
            payload = {
                "jsonrpc": "2.0",
                "id": "test-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": message_id,
                        "role": "user",
                        "parts": [{"type": "text", "text": req.message}],
                    }
                },
            }
            resp = await client.post(agent.url, json=payload, headers=headers)
            resp.raise_for_status()
            response_data = resp.json()

            # Update health status
            agent.is_healthy = True
            agent.last_health_check = datetime.utcnow()
            await db.commit()

            return {"status": "success", "response": response_data}
    except httpx.HTTPError as e:
        # Update health status on failure
        agent.is_healthy = False
        agent.last_health_check = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {str(e)}")
    except Exception as e:
        agent.is_healthy = False
        agent.last_health_check = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/api/agents/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    req: AgentTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream agent response with real-time status updates."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    import uuid

    # Build headers
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if req.openai_api_key:
        headers["X-OpenAI-API-Key"] = req.openai_api_key
    if req.openai_base_url:
        headers["X-OpenAI-Base-URL"] = req.openai_base_url
    if req.openai_model:
        headers["X-OpenAI-Model"] = req.openai_model
    if req.tavily_api_key:
        headers["X-Tavily-API-Key"] = req.tavily_api_key
    if req.custom_headers:
        for key, value in req.custom_headers.items():
            header_key = key if key.lower().startswith("x-") else f"X-{key}"
            headers[header_key] = value

    message_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": "stream-1",
        "method": "message/stream",
        "params": {
            "message": {
                "messageId": message_id,
                "role": "user",
                "parts": [{"type": "text", "text": req.message}],
            }
        },
    }

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", agent.url, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        yield f"data: {json.dumps({'error': error_text.decode(), 'status_code': resp.status_code})}\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                        else:
                            yield "\n"
        except httpx.HTTPError as e:
            yield f"data: {json.dumps({'error': str(e), 'type': 'connection_error'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'type': 'unexpected_error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/agents/{agent_id}/health")
async def check_agent_health(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check agent health by fetching agent card."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{agent.url}/.well-known/agent.json")
            resp.raise_for_status()

            agent.is_healthy = True
            agent.last_health_check = datetime.utcnow()
            await db.commit()
            return {"status": "healthy", "url": agent.url}
    except Exception:
        agent.is_healthy = False
        agent.last_health_check = datetime.utcnow()
        await db.commit()
        return {"status": "unhealthy", "url": agent.url}


def run():
    """Entry point for agent-hub CLI."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
