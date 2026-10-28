import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";
export default function Icon() {
  return new ImageResponse(
    <div
      style={{
        background: "#24664f",
        color: "white",
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 50,
        fontWeight: 800,
        borderRadius: 16,
        paddingBottom: 6,
      }}
    >
      w
    </div>,
    size,
  );
}
