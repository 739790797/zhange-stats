import { useState } from "react";
import { Segmented } from "antd";
import { SklandGameEventsPanel } from "@/components/SklandGameEventsPanel";
import { ArknightsBoxCompare } from "./ArknightsBoxCompare";
import { ArknightsRoguePanel } from "./ArknightsRoguePanel";

type Pane = "calendar" | "compare" | "rogue";

type Props = {
  rogueEnabled?: boolean;
};

export function ArknightsTabPanel({ rogueEnabled = true }: Props) {
  const [pane, setPane] = useState<Pane>("calendar");

  const options = [
    { label: "活动日历", value: "calendar" as const },
    { label: "善意对比", value: "compare" as const },
    { label: "集成战略", value: "rogue" as const },
  ];

  return (
    <div>
      <Segmented
        style={{ marginBottom: 16 }}
        value={pane}
        options={options}
        onChange={(v) => setPane(v as Pane)}
      />
      {pane === "calendar" ? (
        <SklandGameEventsPanel game="arknights" />
      ) : pane === "rogue" ? (
        <ArknightsRoguePanel enabled={rogueEnabled} />
      ) : (
        <ArknightsBoxCompare />
      )}
    </div>
  );
}
