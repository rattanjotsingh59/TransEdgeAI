import React, { useState } from 'react';
import { 
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";

interface SimplifiedTimeframeSelectorProps {
  onTimeframeChange: (hours: string, unit: 'hours' | 'days') => void;
  defaultValue?: string;
  defaultUnit?: 'hours' | 'days';
  isLoading?: boolean;
}

export const SimplifiedTimeframeSelector: React.FC<SimplifiedTimeframeSelectorProps> = ({ 
  onTimeframeChange,
  defaultValue = '24',
  defaultUnit = 'hours',
  isLoading = false,
}) => {
  const [timeUnit, setTimeUnit] = useState<'hours' | 'days'>(defaultUnit);
  const [timeValue, setTimeValue] = useState<string>(defaultValue);

  const handleTimeValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value === '' || /^\d+$/.test(value)) {
      setTimeValue(value);
      onTimeframeChange(value, timeUnit);
    }
  };

  const handleUnitChange = (value: 'hours' | 'days') => {
    setTimeUnit(value);
    onTimeframeChange(timeValue, value);
  };

  return (
    <div className="flex items-center space-x-2">
      <Input
        type="number"
        min="1"
        value={timeValue}
        onChange={handleTimeValueChange}
        className="w-20"
        placeholder="Time"
        disabled={isLoading}
      />
      <Select 
        value={timeUnit} 
        onValueChange={handleUnitChange}
        disabled={isLoading}
      >
        <SelectTrigger className="w-24">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="hours">Hours</SelectItem>
            <SelectItem value="days">Days</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};