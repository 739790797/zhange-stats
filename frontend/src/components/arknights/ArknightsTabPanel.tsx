import { useState } from "react";
import { Segmented } from "antd";
import { ArknightsBoxCompare } from "./ArknightsBoxCompare";
import { ArknightsRoguePanel } from "./ArknightsRoguePanel";

type Pane = "compare" | "rogue";

type Props = {
  rogueEnabled?: boolean;
};

export function ArknightsTabPanel({ rogueEnabled = true }: Props) {
  const [pane, setPane] = useState<Pane>("compare");

  return (
    <div>
      <Segmented
        style={{ marginBottom: 16 }}
        value={pane}
        options={[
          { label: "善意对比", value: "compare" },
          { label: "集成战略", value: "rogue" },
        ]}
        onChange={(v) => setPane(v as Pane)}
      />
      {pane === "rogue" ? (
        <ArknightsRoguePanel enabled={rogueEnabled} />
      ) : (
        <ArknightsBoxCompare />
      )}
    </div>
  );
}
