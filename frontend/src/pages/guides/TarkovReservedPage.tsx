import { ConfigProvider, Result } from "antd";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";

type Props = {
  title: string;
};

/** 预留：tasks / maps 等与 items 平级的上游域。 */
export default function TarkovReservedPage({ title }: Props) {
  return (
    <TarkovGuideShell>
      <ConfigProvider theme={TARKOV_ANTD_DARK}>
        <Result
          status="info"
          title="即将推出"
          subTitle={`${title}数据域已预留，同步与页面尚未接入。`}
        />
      </ConfigProvider>
    </TarkovGuideShell>
  );
}
