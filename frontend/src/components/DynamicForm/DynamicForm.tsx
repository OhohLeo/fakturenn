/**
 * DynamicForm - JSON Schema driven form component.
 *
 * Uses AJV for validation and renders shadcn/ui components based on schema.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { LoadingButton } from "@/components/ui/loading-button";

export interface JSONSchema {
  type: string;
  title?: string;
  description?: string;
  properties?: Record<string, JSONSchemaProperty>;
  required?: string[];
  default?: unknown;
}

export interface JSONSchemaProperty {
  type: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: (string | number)[];
  enumLabels?: Record<string, string>;
  format?: string;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  pattern?: string;
  properties?: Record<string, JSONSchemaProperty>;
  items?: JSONSchemaProperty;
}

interface DynamicFormProps {
  schema: JSONSchema;
  defaultValues?: Record<string, unknown>;
  onSubmit: (data: Record<string, unknown>) => void | Promise<void>;
  submitLabel?: string;
  loading?: boolean;
}

/**
 * Convert JSON Schema to Zod schema for validation.
 */
function jsonSchemaToZod(schema: JSONSchema): z.ZodObject<Record<string, z.ZodTypeAny>> {
  const shape: Record<string, z.ZodTypeAny> = {};
  const required = schema.required || [];

  if (schema.properties) {
    for (const [key, prop] of Object.entries(schema.properties)) {
      let zodType: z.ZodTypeAny;
      const propType = Array.isArray(prop.type) ? prop.type[0] : prop.type;

      switch (propType) {
        case "string":
          zodType = z.string();
          if (prop.minLength) zodType = (zodType as z.ZodString).min(prop.minLength);
          if (prop.maxLength) zodType = (zodType as z.ZodString).max(prop.maxLength);
          if (prop.pattern) zodType = (zodType as z.ZodString).regex(new RegExp(prop.pattern));
          if (prop.enum) zodType = z.enum(prop.enum as [string, ...string[]]);
          break;
        case "number":
        case "integer":
          zodType = z.number();
          if (prop.minimum !== undefined) zodType = (zodType as z.ZodNumber).min(prop.minimum);
          if (prop.maximum !== undefined) zodType = (zodType as z.ZodNumber).max(prop.maximum);
          break;
        case "boolean":
          zodType = z.boolean();
          break;
        case "array":
          zodType = z.array(z.unknown());
          break;
        case "object":
          zodType = z.record(z.string(), z.unknown());
          break;
        default:
          zodType = z.unknown();
      }

      // Make optional if not required
      if (!required.includes(key)) {
        zodType = zodType.optional();
      }

      // Handle null type
      if (Array.isArray(prop.type) && prop.type.includes("null")) {
        zodType = zodType.nullable();
      }

      shape[key] = zodType;
    }
  }

  return z.object(shape);
}

/**
 * Render a form field based on JSON Schema property.
 */
function renderField(
  key: string,
  prop: JSONSchemaProperty,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  control: any,
) {
  const propType = Array.isArray(prop.type) ? prop.type[0] : prop.type;
  const label = prop.title || key;
  const description = prop.description;

  // Handle enum (select)
  if (prop.enum) {
    return (
      <FormField
        key={key}
        control={control}
        name={key}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <Select onValueChange={field.onChange} defaultValue={field.value as string}>
              <FormControl>
                <SelectTrigger>
                  <SelectValue placeholder={`Select ${label.toLowerCase()}`} />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {prop.enum!.map((value) => (
                  <SelectItem key={String(value)} value={String(value)}>
                    {prop.enumLabels?.[String(value)] || String(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {description && <FormDescription>{description}</FormDescription>}
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  // Handle boolean (checkbox)
  if (propType === "boolean") {
    return (
      <FormField
        key={key}
        control={control}
        name={key}
        render={({ field }) => (
          <FormItem className="flex flex-row items-start space-x-3 space-y-0">
            <FormControl>
              <Checkbox
                checked={field.value as boolean}
                onCheckedChange={field.onChange}
              />
            </FormControl>
            <div className="space-y-1 leading-none">
              <FormLabel>{label}</FormLabel>
              {description && <FormDescription>{description}</FormDescription>}
            </div>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  // Handle multiline strings (textarea)
  if (propType === "string" && prop.format === "textarea") {
    return (
      <FormField
        key={key}
        control={control}
        name={key}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Textarea
                placeholder={prop.default as string || ""}
                {...field}
                value={field.value as string || ""}
              />
            </FormControl>
            {description && <FormDescription>{description}</FormDescription>}
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  // Handle numbers
  if (propType === "number" || propType === "integer") {
    return (
      <FormField
        key={key}
        control={control}
        name={key}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input
                type="number"
                placeholder={prop.default !== undefined ? String(prop.default) : ""}
                {...field}
                value={field.value as number || ""}
                onChange={(e) => field.onChange(e.target.valueAsNumber || undefined)}
              />
            </FormControl>
            {description && <FormDescription>{description}</FormDescription>}
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  // Handle password
  if (propType === "string" && prop.format === "password") {
    return (
      <FormField
        key={key}
        control={control}
        name={key}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input
                type="password"
                placeholder=""
                {...field}
                value={field.value as string || ""}
              />
            </FormControl>
            {description && <FormDescription>{description}</FormDescription>}
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  // Default: string input
  return (
    <FormField
      key={key}
      control={control}
      name={key}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input
              placeholder={prop.default as string || ""}
              {...field}
              value={field.value as string || ""}
            />
          </FormControl>
          {description && <FormDescription>{description}</FormDescription>}
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

export function DynamicForm({
  schema,
  defaultValues = {},
  onSubmit,
  submitLabel = "Submit",
  loading = false,
}: DynamicFormProps) {
  // Build default values from schema
  const schemaDefaults: Record<string, unknown> = {};
  if (schema.properties) {
    for (const [key, prop] of Object.entries(schema.properties)) {
      if (prop.default !== undefined) {
        schemaDefaults[key] = prop.default;
      }
    }
  }

  const zodSchema = jsonSchemaToZod(schema);

  const form = useForm({
    resolver: zodResolver(zodSchema),
    defaultValues: { ...schemaDefaults, ...defaultValues },
  });

  const handleSubmit = form.handleSubmit(async (data) => {
    await onSubmit(data);
  });

  if (!schema.properties) {
    return <div>No fields defined in schema</div>;
  }

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {Object.entries(schema.properties).map(([key, prop]) =>
          renderField(key, prop, form.control)
        )}
        <div className="flex justify-end">
          <LoadingButton type="submit" loading={loading}>
            {submitLabel}
          </LoadingButton>
        </div>
      </form>
    </Form>
  );
}

export default DynamicForm;
