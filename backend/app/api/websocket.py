"""
WebSocket connection manager for real-time signal updates
Includes heartbeat/keepalive mechanism for connection health monitoring
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional
import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

# Heartbeat configuration
PING_INTERVAL = 30  # seconds
PING_TIMEOUT = 10  # seconds to wait for pong


class ConnectionManager:
    """Manages WebSocket connections with heartbeat/keepalive support"""
    
    def __init__(self, ping_interval: int = PING_INTERVAL):
        self.active_connections: List[WebSocket] = []
        self.connection_ids: Dict[WebSocket, str] = {}
        self.connection_timestamps: Dict[WebSocket, float] = {}  # Last activity time
        self.ping_interval = ping_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start_heartbeat(self):
        """Start the heartbeat task for monitoring connection health"""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocket heartbeat task started")
    
    async def stop_heartbeat(self):
        """Stop the heartbeat task"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket heartbeat task stopped")
    
    async def _heartbeat_loop(self):
        """Periodic heartbeat to check connection health"""
        while self._running:
            await asyncio.sleep(self.ping_interval)
            await self._send_heartbeats()
    
    async def _send_heartbeats(self):
        """Send ping to all connections and clean up stale ones"""
        stale_connections = []
        current_time = time.time()
        
        for websocket in self.active_connections:
            try:
                # Send ping - wait for pong response
                await asyncio.wait_for(
                    websocket.send_json({"type": "ping", "timestamp": current_time}),
                    timeout=PING_TIMEOUT
                )
                # Update last activity
                self.connection_timestamps[websocket] = current_time
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket ping timeout, marking as stale")
                stale_connections.append(websocket)
            except WebSocketDisconnect:
                stale_connections.append(websocket)
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}")
                stale_connections.append(websocket)
        
        # Clean up stale connections
        for ws in stale_connections:
            await self._cleanup_connection(ws, "heartbeat_timeout")
    
    async def _cleanup_connection(self, websocket: WebSocket, reason: str):
        """Clean up a disconnected/failed connection"""
        try:
            await websocket.close(code=1001, reason=reason)
        except Exception:
            pass
        self.disconnect(websocket)
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_ids[websocket] = client_id
        self.connection_timestamps[websocket] = time.time()
        logger.info(f"WebSocket client connected: {client_id}")
        logger.info(f"Total active connections: {len(self.active_connections)}")
        
        # Start heartbeat if not already running
        if not self._running:
            await self.start_heartbeat()
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        client_id = self.connection_ids.get(websocket, "unknown")
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_ids:
            del self.connection_ids[websocket]
        if websocket in self.connection_timestamps:
            del self.connection_timestamps[websocket]
        logger.info(f"WebSocket client disconnected: {client_id} (reason: client_disconnect)")
        logger.info(f"Total active connections: {len(self.active_connections)}")
        
        # Stop heartbeat if no connections
        if not self.active_connections and self._running:
            asyncio.create_task(self.stop_heartbeat())
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
            self.connection_timestamps[websocket] = time.time()
        except WebSocketDisconnect:
            await self._cleanup_connection(websocket, "send_failed")
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        current_time = time.time()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                self.connection_timestamps[connection] = current_time
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            await self._cleanup_connection(connection, "broadcast_failed")
    
    async def broadcast_signal(self, signal_data: dict):
        """Broadcast a new signal to all clients"""
        message = {
            "type": "new_signal",
            "data": signal_data
        }
        await self.broadcast(message)
        logger.info(f"Broadcasted new signal: {signal_data.get('symbol')}")
    
    async def broadcast_update(self, update_type: str, data: dict):
        """Broadcast a general update to all clients"""
        message = {
            "type": update_type,
            "data": data
        }
        await self.broadcast(message)
    
    def get_connection_info(self) -> dict:
        """Get information about active connections"""
        return {
            "total_connections": len(self.active_connections),
            "heartbeat_running": self._running,
            "ping_interval": self.ping_interval,
        }


# Global connection manager instance
manager = ConnectionManager()
