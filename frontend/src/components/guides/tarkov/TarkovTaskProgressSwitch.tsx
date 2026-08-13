import { Switch } from "antd";
import styles from "./TarkovTaskProgressSwitch.module.css";

type Props = {
  enabled: boolean;
  onChange: (value: boolean) => void;
};

export function TarkovTaskProgressSwitch({ enabled, onChange }: Props) {
  return (
    <label className={styles.row}>
      <Switch size="small" checked={enabled} onChange={onChange} />
      <span>按我的进度</span>
    </label>
  );
}
