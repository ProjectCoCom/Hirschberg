/**
 * Summary: React UI component 'Primaryviewrouter'.
 *
 * What it does: Renders the 'Primaryviewrouter' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import type { ComponentProps, ReactNode } from "react";

import type { PrimaryNavIndex } from "../app/constants";
import type { UseMonitorRuntimeResult } from "../app/hooks/useMonitorRuntime";
import { ActivityPrimaryView } from "./ActivityPrimaryView";
import { ApisPrimaryView } from "./ApisPrimaryView";
import { CanvasPrimaryView } from "./CanvasPrimaryView";
import { ChatPrimaryView } from "./ChatPrimaryView";
import { PromptsPrimaryView } from "./PromptsPrimaryView";
import { ReposPrimaryView } from "./ReposPrimaryView";
import { SettingsPrimaryView } from "./SettingsPrimaryView";
import { UsagePrimaryView } from "./UsagePrimaryView";

type PrimaryViewRouterProps = {
  activePrimaryNav: PrimaryNavIndex;
  isMonitorVisible: boolean;
  activityPrimaryViewProps: ComponentProps<typeof ActivityPrimaryView>;
  settingsPrimaryViewProps: ComponentProps<typeof SettingsPrimaryView>;
  canvasPrimaryViewProps: ComponentProps<typeof CanvasPrimaryView>;
  monitorRuntime: Pick<
    UseMonitorRuntimeResult,
    | "monitorConfig"
    | "monitorFeed"
    | "monitorError"
    | "isRefreshingMonitorFeed"
    | "isSavingMonitorConfig"
    | "refreshMonitorFeed"
    | "patchMonitorConfig"
  >;
  conversationsEnabled: boolean;
  onConversationsSidebarContent: (content: ReactNode) => void;
  onConversationsActionPanel: (content: ReactNode) => void;
  promptsEnabled: boolean;
  onPromptsSidebarContent: (content: ReactNode) => void;
};

export const PrimaryViewRouter = ({
  activePrimaryNav,
  isMonitorVisible,
  activityPrimaryViewProps,
  settingsPrimaryViewProps,
  canvasPrimaryViewProps,
  monitorRuntime,
  conversationsEnabled,
  onConversationsSidebarContent,
  onConversationsActionPanel,
  promptsEnabled,
  onPromptsSidebarContent,
}: PrimaryViewRouterProps) => {
  return (
    <>
      {/* Chat stays mounted to preserve dropdown/model state across tab switches */}
      <div style={{ display: activePrimaryNav === 4 ? "contents" : "none" }}>
        <ChatPrimaryView />
      </div>
      {activePrimaryNav === 2 && <ReposPrimaryView />}
      {activePrimaryNav === 3 && <ActivityPrimaryView {...activityPrimaryViewProps} />}
      {activePrimaryNav === 5 && (
        <PromptsPrimaryView enabled={promptsEnabled} onSidebarContent={onPromptsSidebarContent} />
      )}
      {activePrimaryNav === 6 && <ApisPrimaryView />}
      {activePrimaryNav === 7 && <UsagePrimaryView />}
      {activePrimaryNav === 8 && <SettingsPrimaryView {...settingsPrimaryViewProps} />}
      {activePrimaryNav === 1 && <CanvasPrimaryView {...canvasPrimaryViewProps} />}
    </>
  );
};
