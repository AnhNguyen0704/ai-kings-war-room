import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import LobbyPage from "./pages/LobbyPage";
import RoomPage from "./pages/RoomPage";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LobbyPage />} />
        <Route path="/rooms/:roomId" element={<RoomPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
