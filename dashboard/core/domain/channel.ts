/**
 * Summary: Domain model definitions for 'Channel'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Channel' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
 */



export type ChannelMessage = {
  messageId: string;
  fromTerminalId: string;
  toTerminalId: string;
  content: string;
  timestamp: string;
  delivered: boolean;
};
