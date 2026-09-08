import { describe, expect, it, vi } from "vitest";
import {
  adminCanStepUp,
  adminStepUpRequired,
  requestAdminStepUp,
} from "./adminCanStepUp";

describe("adminCanStepUp", () => {
  it("requires a verified email when step-up is on", () => {
    expect(adminCanStepUp(null)).toBe(false);
    expect(adminCanStepUp({ email: "a@b.c", email_verified: false })).toBe(false);
    expect(adminCanStepUp({ email: "a@b.c", email_verified: true })).toBe(true);
  });

  it("skips the email check when the backend says step-up is off", () => {
    expect(adminCanStepUp({ admin_step_up_required: false })).toBe(true);
  });
});

describe("adminStepUpRequired", () => {
  it("treats a missing flag as required", () => {
    expect(adminStepUpRequired(null)).toBe(true);
    expect(adminStepUpRequired({ email: "a@b.c", email_verified: true })).toBe(
      true,
    );
  });

  it("is off only when the backend sends false", () => {
    expect(adminStepUpRequired({ admin_step_up_required: false })).toBe(false);
    expect(adminStepUpRequired({ admin_step_up_required: true })).toBe(true);
  });
});

describe("requestAdminStepUp", () => {
  it("skips the modal when the backend says step-up is off", () => {
    const onNeedCode = vi.fn();
    const onSkip = vi.fn();
    requestAdminStepUp(
      { admin_step_up_required: false },
      { onNeedCode, onSkip },
    );
    expect(onSkip).toHaveBeenCalledOnce();
    expect(onNeedCode).not.toHaveBeenCalled();
  });

  it("opens the modal in production when email is verified", () => {
    const onNeedCode = vi.fn();
    const onSkip = vi.fn();
    requestAdminStepUp(
      {
        email: "a@b.c",
        email_verified: true,
        admin_step_up_required: true,
      },
      { onNeedCode, onSkip },
    );
    expect(onNeedCode).toHaveBeenCalledOnce();
    expect(onSkip).not.toHaveBeenCalled();
  });
});
