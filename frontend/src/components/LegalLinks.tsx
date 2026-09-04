import { Typography } from "antd";
import { Link } from "react-router-dom";
import { LEGAL_PRIVACY_PATH, LEGAL_TERMS_PATH } from "@/lib/legalDocs";

type Props = {
  /** 如「登录即表示同意」 */
  prefix?: string;
};

export function LegalLinks({ prefix }: Props) {
  return (
    <Typography.Paragraph
      type="secondary"
      style={{
        textAlign: "center",
        marginTop: 16,
        marginBottom: 0,
        fontSize: 12,
      }}
    >
      {prefix ? `${prefix} ` : null}
      <Link to={LEGAL_TERMS_PATH}>服务条款</Link>
      {" · "}
      <Link to={LEGAL_PRIVACY_PATH}>隐私说明</Link>
    </Typography.Paragraph>
  );
}
