import {
  CheckOutlined,
  CloseOutlined,
  DeploymentUnitOutlined,
  FlagOutlined,
  QuestionOutlined,
  SafetyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Popover, type PopoverProps } from "antd";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { StrongholdScope } from "@/features/platforms/skland/api/strongholdApi";
import { modeLabels } from "./strongholdLabels";
import styles from "./ArknightsStronghold.module.css";
import reportStyles from "./StrongholdReport.module.css";

const modeIcons = {
  single: UserOutlined,
  multi: DeploymentUnitOutlined,
  local: FlagOutlined,
};

export function BattleScope({
  scope,
  version,
}: {
  scope: StrongholdScope;
  version?: string | null;
}) {
  const ModeIcon = scope.mode_type ? modeIcons[scope.mode_type] : null;
  return (
    <span className={styles.scopeLine}>
      {scope.mode_type && ModeIcon ? (
        <span>
          <ModeIcon /> {modeLabels[scope.mode_type]}
        </span>
      ) : null}
      <span className={styles.difficulty} data-abyss={scope.difficulty_id === "abyss"}>
        {scope.difficulty_label}
      </span>
      <span>{version ?? scope.season_label}</span>
    </span>
  );
}

export function ResultMark({ result }: { result: boolean | null }) {
  return (
    <span
      className={styles.result}
      data-result={result == null ? "unknown" : result ? "win" : "loss"}
    >
      {result == null ? <QuestionOutlined /> : result ? <CheckOutlined /> : <CloseOutlined />}
      {result == null ? "结果未知" : result ? "模拟完成" : "模拟中断"}
    </span>
  );
}

export function BattleIcon({
  src,
  kind,
  fallback = <SafetyOutlined />,
}: {
  src?: string | null;
  kind?: "bond" | "strategy";
  fallback?: ReactNode;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <span className={styles.battleIcon} data-kind={kind} aria-hidden="true">
      {src && src !== failed ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(src)}
        />
      ) : (
        fallback
      )}
    </span>
  );
}

export function EffectPopup({
  className,
  label,
  children,
  content,
  placement = "top",
}: {
  className: string;
  label: string;
  children: ReactNode;
  content: ReactNode;
  placement?: PopoverProps["placement"];
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const pinned = useRef(false);
  const restoringFocus = useRef(false);
  const [open, setOpen] = useState(false);
  const [fitsRight, setFitsRight] = useState(false);
  const checkRight = useCallback(() => {
    if (placement !== "right" || !trigger.current) return;
    const width = document.documentElement.clientWidth;
    setFitsRight(
      width - trigger.current.getBoundingClientRect().right >= Math.min(415, width - 46) + 16,
    );
  }, [placement]);
  const show = () => {
    checkRight();
    setOpen(true);
  };
  const cancelClose = () => clearTimeout(timer.current);
  const closeSoon = () => {
    cancelClose();
    timer.current = setTimeout(() => {
      if (
        !pinned.current &&
        !popup.current?.contains(document.activeElement) &&
        !trigger.current?.matches(":focus-visible")
      ) {
        setOpen(false);
      }
    }, 150);
  };

  useEffect(() => {
    if (!open) return;
    const dismiss = () => {
      clearTimeout(timer.current);
      pinned.current = false;
      setOpen(false);
    };
    const outside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !trigger.current?.contains(event.target) &&
        !popup.current?.contains(event.target)
      ) {
        dismiss();
      }
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (popup.current?.contains(document.activeElement)) {
        restoringFocus.current = true;
        trigger.current?.focus({ preventScroll: true });
        restoringFocus.current = false;
      }
      dismiss();
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("resize", checkRight);
    return () => {
      clearTimeout(timer.current);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("resize", checkRight);
    };
  }, [open, checkRight]);

  return (
    <Popover
      placement={placement === "right" && !fitsRight ? "bottom" : placement}
      color="#152326"
      trigger={[]}
      open={open}
      destroyTooltipOnHide
      rootClassName={reportStyles.effectPopover}
      content={
        <div
          className={reportStyles.effectContent}
          ref={popup}
          id={id}
          tabIndex={-1}
          onPointerEnter={cancelClose}
          onPointerLeave={closeSoon}
          onBlur={(event) => {
            if (
              !event.currentTarget.contains(event.relatedTarget) &&
              event.relatedTarget !== trigger.current
            ) {
              pinned.current = false;
              setOpen(false);
            }
          }}
        >
          {content}
        </div>
      }
    >
      <button
        ref={trigger}
        type="button"
        className={className}
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onPointerEnter={(event) => {
          if (event.pointerType !== "mouse") return;
          cancelClose();
          show();
        }}
        onPointerLeave={(event) => {
          if (event.pointerType === "mouse") closeSoon();
        }}
        onFocus={(event) => {
          if (!restoringFocus.current && event.currentTarget.matches(":focus-visible")) {
            cancelClose();
            show();
          }
        }}
        onBlur={(event) => {
          if (popup.current?.contains(event.relatedTarget)) return;
          pinned.current = false;
          closeSoon();
        }}
        onClick={() => {
          cancelClose();
          pinned.current = !pinned.current;
          if (pinned.current) show();
          else setOpen(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && popup.current) {
            event.preventDefault();
            popup.current.focus({ preventScroll: true });
          }
        }}
      >
        {children}
      </button>
    </Popover>
  );
}

export function StrategyMark({
  icon,
  name,
  description,
}: {
  icon?: string | null;
  name?: string | null;
  description?: string | null;
}) {
  const title = name || "策略未记录";
  const mark = <BattleIcon kind="strategy" src={icon} fallback={<FlagOutlined />} />;
  const label = (
    <>
      {mark}
      <span>{title}</span>
    </>
  );
  if (!name && !icon && !description)
    return <span className={styles.historyStrategy}>{label}</span>;
  return (
    <EffectPopup
      className={styles.historyStrategy}
      label={`策略：${title}`}
      placement="right"
      content={
        <>
          <div className={reportStyles.effectHeading}>
            {mark}
            <strong>{title}</strong>
          </div>
          <p className={reportStyles.effectText}>{description || "同版本策略效果未收录"}</p>
        </>
      }
    >
      {label}
    </EffectPopup>
  );
}
