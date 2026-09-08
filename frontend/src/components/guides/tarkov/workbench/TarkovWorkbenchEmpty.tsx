import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  onAdd: () => void;
};

export function TarkovWorkbenchEmpty({ onAdd }: Props) {
  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.addGun}
        onClick={onAdd}
        aria-label="选枪"
      >
        <span className={styles.addGunPlus} aria-hidden>
          +
        </span>
        <span className={styles.addGunLabel}>选枪</span>
      </button>
    </div>
  );
}
