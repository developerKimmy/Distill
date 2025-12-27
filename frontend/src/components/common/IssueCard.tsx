import { memo } from 'react';
import { Link } from 'react-router-dom';
import { FollowButton } from './FollowButton';
import { formatShortDate } from '../../utils/dateFormat';
import type { Issue } from '../../types';

interface IssueCardProps {
  issue: Issue;
  onFollowClick: (e: React.MouseEvent, issue: Issue) => void;
}

function IssueCardComponent({ issue, onFollowClick }: IssueCardProps) {
  return (
    <Link
      to={`/issues/${issue.id}`}
      className="block bg-white rounded-lg border border-gray-200 p-3 sm:p-4 hover:border-amber-300 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate text-sm sm:text-base">
            {issue.name}
          </h3>
          <p className="text-xs sm:text-sm text-gray-500 mt-1">
            {formatShortDate(issue.firstSeenAt)} ~ {formatShortDate(issue.lastSeenAt)}
            <span className="ml-2">({issue.totalSnapshots}일)</span>
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {issue.latestArticleCount && (
            <span className="text-xs sm:text-sm text-amber-600 font-medium whitespace-nowrap">
              기사 {issue.latestArticleCount}개
            </span>
          )}
          <FollowButton
            isFollowing={issue.isFollowing ?? false}
            onClick={(e) => onFollowClick(e, issue)}
          />
        </div>
      </div>
    </Link>
  );
}

export const IssueCard = memo(IssueCardComponent);
