"use client";

interface TextDisplayProps {
  text: string;
  /** 儿童阅读用大字号，默认 true */
  largeForKids?: boolean;
}

export default function TextDisplay({ text, largeForKids = true }: TextDisplayProps) {
  return (
    <p
      className={`text-text-story leading-relaxed whitespace-pre-wrap ${
        largeForKids ? "text-xl md:text-2xl leading-loose" : ""
      }`}
    >
      {text}
    </p>
  );
}
