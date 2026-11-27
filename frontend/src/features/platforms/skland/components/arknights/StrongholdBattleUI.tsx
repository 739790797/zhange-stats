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
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
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
  className,
  fallback = <SafetyOutlined />,
}: {
  src?: string | null;
  kind?: "bond" | "strategy";
  className?: string;
  fallback?: ReactNode;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <span className={className ?? styles.battleIcon} data-kind={kind} aria-hidden="true">
      {src && src !== failed ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(src)}
        />
      ) : (
        fallback
      )}
    </span>
  );
}

const effectMaxWidth = 520;

export function EffectPopup({
  className,
  label,
  children,
  content,
  placement = "top",
  tone = "dark",
  onOpenChange,
}: {
  className: string;
  label: string;
  children: ReactNode;
  content: ReactNode;
  placement?: PopoverProps["placement"];
  tone?: "dark" | "paper";
  onOpenChange?: (open: boolean) => void;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const pinned = useRef(false);
  const restoringFocus = useRef(false);
  const [open, setOpen] = useState(false);
  const [hasSideRoom, setHasSideRoom] = useState(false);
  const checkSideRoom = useCallback(() => {
    if (placement !== "right" || !trigger.current) return;
    const width = document.documentElement.clientWidth;
    const rect = trigger.current.getBoundingClientRect();
    const needed = Math.min(effectMaxWidth, width - 32) + 16;
    setHasSideRoom(Math.max(width - rect.right, rect.left) >= needed);
  }, [placement]);
  const show = () => {
    checkSideRoom();
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
    window.addEventListener("resize", checkSideRoom);
    return () => {
      clearTimeout(timer.current);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("resize", checkSideRoom);
    };
  }, [open, checkSideRoom]);

  useEffect(() => {
    if (!open || !onOpenChange) return;
    onOpenChange(true);
    return () => onOpenChange(false);
  }, [open, onOpenChange]);

  // The placement offset is kept when Ant shifts the bubble at viewport edges.
  return (
    <Popover
      placement={placement === "right" && !hasSideRoom ? "bottom" : placement}
      align={{ offset: [0, 0] }}
      color={tone === "paper" ? "#fffdf7" : "#152326"}
      trigger={[]}
      open={open}
      destroyTooltipOnHide
      rootClassName={tone === "paper" ? reportStyles.paperPopover : reportStyles.effectPopover}
      content={
        <div
          className={reportStyles.effectViewport}
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
          <div
            className={reportStyles.effectContent}
            style={{ "--effect-max-width": `${effectMaxWidth}px` } as CSSProperties}
          >
            {content}
          </div>
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
