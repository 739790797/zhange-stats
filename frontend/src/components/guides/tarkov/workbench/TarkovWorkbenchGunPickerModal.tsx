import { Modal } from "antd";
import { TarkovGunsPanel } from "@/components/guides/tarkov/TarkovGunsPanel";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  open: boolean;
  onCancel: () => void;
  onPick: (gunId: string) => void;
};

export function TarkovWorkbenchGunPickerModal({
  open,
  onCancel,
  onPick,
}: Props) {
  return (
    <Modal
      open={open}
      title="选枪"
      footer={null}
      destroyOnClose
      centered
      width={1100}
      className={styles.gunPickModal}
      classNames={{
        body: styles.gunPickModalBody,
        content: styles.gunPickModalContent,
      }}
      onCancel={onCancel}
    >
      <TarkovGunsPanel compact onPick={onPick} />
    </Modal>
  );
}
