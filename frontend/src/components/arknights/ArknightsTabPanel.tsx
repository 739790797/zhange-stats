import { useState } from "react";
import { Segmented } from "antd";
import { ArknightsBoxCompare } from "./ArknightsBoxCompare";
import { ArknightsMaaPanel } from "./ArknightsMaaPanel";
import { ArknightsRoguePanel } from "./ArknightsRoguePanel";

type Pane = "compare" | "rogue" | "maa";

type Props = {
  rogueEnabled?: boolean;
  maaEnabled?: boolean;
};

export function ArknightsTabPanel({
  rogueEnabled = true,
  maaEnabled = false,
}: Props) {
  const [pane, setPane] = useState<Pane>("compare");

  const options = [
    { label: "善意对比", value: "compare" as const },
    { label: "集成战略", value: "rogue" as const },
    ...(maaEnabled ? [{ label: "MAA", value: "maa" as const }] : []),
  ];

  return (
    <div>
      <Segmented
        style={{ marginBottom: 16 }}
        value={pane}
        options={options}
        onChange={(v) => setPane(v as Pane)}
      />
      {pane === "rogue" ? (
        <ArknightsRoguePanel enabled={rogueEnabled} />
      ) : pane === "maa" ? (
        <ArknightsMaaPanel enabled={rogueEnabled} />
      ) : (
        <ArknightsBoxCompare />
      )}
    </div>
  );
}
