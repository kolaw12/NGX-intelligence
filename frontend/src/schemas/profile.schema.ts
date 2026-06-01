import { z } from "zod";

export const profileSchema = z.object({
  name: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email"),
  organization: z.string().optional(),
  role: z.enum(["retail", "professional", "institutional"]),
});

export const contactSchema = z.object({
  name: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email"),
  organization: z.string().optional(),
  message: z.string().min(20, "Tell us a little more - at least 20 characters"),
});

export type ProfileValues = z.infer<typeof profileSchema>;
export type ContactValues = z.infer<typeof contactSchema>;
