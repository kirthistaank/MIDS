import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../components/ui/button';
import { Sparkles, ArrowRight, Target, GripVertical } from 'lucide-react';

const SKILLS = [
  'Effective Communication',
  'Conflict Resolution',
  'Negotiation and Persuasion',
  'Feedback Receipt and Delivery',
  'Executive Presence',
];

export default function RankSkills() {
  const [rankedSkills, setRankedSkills] = useState<string[]>(SKILLS);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const navigate = useNavigate();

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newSkills = [...rankedSkills];
    const draggedItem = newSkills[draggedIndex];
    newSkills.splice(draggedIndex, 1);
    newSkills.splice(index, 0, draggedItem);

    setRankedSkills(newSkills);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('rankedSkills', JSON.stringify(rankedSkills));
    navigate('/onboarding/other-focus');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="p-8">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Guidepost
          </h1>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Progress indicator */}
          <div className="flex items-center justify-center gap-2 mb-8">
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
          </div>

          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                <Target className="w-8 h-8 text-indigo-600" />
              </div>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">Rank your priorities</h2>
              <p className="text-slate-600">
                Drag to rank these skills from 1 (highest) to 5 (lowest priority)
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-3">
                {rankedSkills.map((skill, index) => (
                  <div
                    key={skill}
                    draggable
                    onDragStart={() => handleDragStart(index)}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragEnd={handleDragEnd}
                    className={`group flex items-center gap-4 p-5 rounded-xl border-2 cursor-move transition-all duration-200 ${
                      draggedIndex === index
                        ? 'border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-lg scale-105'
                        : 'border-slate-200 bg-white hover:border-indigo-200 hover:shadow-md'
                    }`}
                  >
                    <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white font-bold shadow-md">
                      {index + 1}
                    </div>
                    <span className="flex-1 text-slate-900 font-medium">{skill}</span>
                    <GripVertical className="w-5 h-5 text-slate-400 group-hover:text-indigo-600 transition-colors" />
                  </div>
                ))}
              </div>

              <Button className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200">
                Continue
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}