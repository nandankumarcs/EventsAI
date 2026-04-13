import { Ticket, Popcorn, Trophy, Calendar, Music, MapPin, Zap, Flame } from 'lucide-react'

export const PROMPT_POOL = [
  { icon: Popcorn, text: "What action movies are playing this weekend?" },
  { icon: Trophy, text: "Are there any cricket matches in Mumbai next week?" },
  { icon: Ticket, text: "Find comedy shows this weekend" },
  { icon: Calendar, text: "Suggest events under Rs. 1000" },
  { icon: Music, text: "Are there any live music concerts happening today?" },
  { icon: Flame, text: "What are the most popular events in town right now?" },
  { icon: Popcorn, text: "Find a highly-rated sci-fi movie for tomorrow night" },
  { icon: Trophy, text: "Show me upcoming football matches" },
  { icon: MapPin, text: "What's happening in Delhi this Sunday?" },
  { icon: Music, text: "Find EDM festivals or club nights this month" },
  { icon: Calendar, text: "Are there any art exhibitions or theatre plays?" },
  { icon: Zap, text: "Find me some fun weekend activities for kids" },
  { icon: Popcorn, text: "Show me romantic movies playing in IMAX" },
  { icon: Trophy, text: "Are there any tennis tournaments nearby?" },
]

export function getRandomPrompts(count: number = 4) {
  // Shuffle array using Fisher-Yates and slice
  const shuffled = [...PROMPT_POOL]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled.slice(0, count)
}
