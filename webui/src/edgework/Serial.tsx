import { h } from "preact";

type Props = {
  serial: string;
};

export default function Serial({ serial }: Props) {
  return (
    <div className="serial">
      <div className="number">{serial}</div>
    </div>
  );
}
