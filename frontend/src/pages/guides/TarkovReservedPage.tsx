import { ConfigProvider, Result } from "antd";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";

type Props = {
  title: string;
};

/** 预留：maps / 藏身处等尚未接入的上游域。 */
export default function TarkovReservedPage({ title }: Props) {
  return (
    <ConfigProvider theme={TARKOV_ANTD_DARK}>
      <Result
        status="info"
        title="即将推出"
        subTitle={`${title}数据域已预留，同步与页面尚未接入。`}
      />
    </ConfigProvider>
  );
}
