import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  onAdd: () => void;
  onGunsmith?: () => void;
};

export function TarkovWorkbenchEmpty({ onAdd, onGunsmith }: Props) {
  return (
    <div className={styles.emptyChoices}>
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
      {onGunsmith ? (
        <button
          type="button"
          className={styles.addGun}
          onClick={onGunsmith}
          aria-label="枪匠任务"
        >
          <span className={styles.addGunPlus} aria-hidden>
            ⚒
          </span>
          <span className={styles.addGunLabel}>枪匠任务</span>
        </button>
      ) : null}
    </div>
  );
}
