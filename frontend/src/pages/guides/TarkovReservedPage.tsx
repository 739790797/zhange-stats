import { Result } from "antd";

type Props = {
  title: string;
};

/** 预留：maps / 藏身处等尚未接入的上游域。 */
export default function TarkovReservedPage({ title }: Props) {
  return (
    <Result
      status="info"
      title="即将推出"
      subTitle={`${title}数据域已预留，同步与页面尚未接入。`}
    />
  );
}
