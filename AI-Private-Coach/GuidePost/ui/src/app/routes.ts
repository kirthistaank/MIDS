import { createBrowserRouter } from "react-router";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Occupation from "./pages/onboarding/Occupation";
import Title from "./pages/onboarding/Title";
import RankSkills from "./pages/onboarding/RankSkills";
import OtherFocus from "./pages/onboarding/OtherFocus";
import VoiceRecording from "./pages/onboarding/VoiceRecording";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Landing,
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/onboarding/occupation",
    Component: Occupation,
  },
  {
    path: "/onboarding/title",
    Component: Title,
  },
  {
    path: "/onboarding/rank-skills",
    Component: RankSkills,
  },
  {
    path: "/onboarding/other-focus",
    Component: OtherFocus,
  },
  {
    path: "/onboarding/voice-recording",
    Component: VoiceRecording,
  },
  {
    path: "/dashboard",
    Component: Dashboard,
  },
  {
    path: "/chat",
    Component: Chat,
  },
]);