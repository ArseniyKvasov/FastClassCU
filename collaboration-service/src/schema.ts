import {
  getSchema,
  type Extensions,
  type JSONContent,
} from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import Underline from "@tiptap/extension-underline";
import { prosemirrorJSONToYDoc, yDocToProsemirrorJSON } from "y-prosemirror";
import * as Y from "yjs";

import { settings } from "./config.js";

const extensions: Extensions = [
  // TipTap 3's StarterKit bundles its own Underline mark now - disable it
  // and register the standalone package explicitly instead of letting both
  // register under the same name. A duplicate-name schema is exactly the
  // kind of ambiguity that must never leak into the ProseMirror<->Yjs
  // projection this service exists to get right.
  StarterKit.configure({
    heading: false,
    underline: false,
  }),
  TableKit.configure({
    table: {
      resizable: false,
      allowTableNodeSelection: false,
      renderWrapper: true,
    },
  }),
  Underline,
];

const schema = getSchema(extensions);

export function emptyDocumentJson(): JSONContent {
  return {
    type: "doc",
    content: [
      {
        type: "paragraph",
      },
    ],
  };
}

export function jsonToYDoc(
  content: JSONContent | null | undefined,
  fieldName = settings.roomFieldName,
): Y.Doc {
  return prosemirrorJSONToYDoc(schema, content ?? emptyDocumentJson(), fieldName);
}

export function yDocToJson(
  document: Y.Doc,
  fieldName = settings.roomFieldName,
): JSONContent {
  return yDocToProsemirrorJSON(document, fieldName) as JSONContent;
}

export function extractPlainText(node: JSONContent | JSONContent[] | string | null | undefined): string {
  if (node == null) {
    return "";
  }
  if (typeof node === "string") {
    return node;
  }
  if (Array.isArray(node)) {
    return node.map((item) => extractPlainText(item)).join("");
  }

  if (node.type === "text") {
    return String(node.text ?? "");
  }

  if (node.type === "hardBreak") {
    return "\n";
  }

  const content = Array.isArray(node.content) ? node.content : [];
  const inner = content.map((item) => extractPlainText(item)).join("");
  if (
    node.type === "paragraph" ||
    node.type === "heading" ||
    node.type === "listItem" ||
    node.type === "tableRow"
  ) {
    return `${inner}\n`;
  }
  return inner;
}
