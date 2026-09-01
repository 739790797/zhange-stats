import { createContext } from "react";

export type GoonLiveValue = {
  live: boolean;
};

export const TarkovGoonTrackerLiveContext = createContext<GoonLiveValue>({
  live: false,
});

export function goonsQueryKey(mode: string) {
  return ["guides-tarkov-goons", mode] as const;
}
