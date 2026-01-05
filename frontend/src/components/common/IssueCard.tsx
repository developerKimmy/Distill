import { memo } from 'react';
import { Link } from 'react-router-dom';
import { FollowButton } from './FollowButton';
import { formatShortDate } from '../../utils/dateFormat';
import type { IssueListItem } from '../../types';

interface IssueCardProps {
  issue: IssueListItem;
  onFollowClick: (e: React.MouseEvent, issue: IssueListItem) => void;
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
            {issue.firstSeenAt && formatShortDate(issue.firstSeenAt)}
            {issue.firstSeenAt && issue.lastSeenAt && ' ~ '}
            {issue.lastSeenAt && formatShortDate(issue.lastSeenAt)}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {issue.articleCount > 0 && (
            <span className="text-xs sm:text-sm text-amber-600 font-medium whitespace-nowrap">
              기사 {issue.articleCount}개
            </span>
          )}
          <FollowButton
            isFollowing={issue.isFollowing}
            onClick={(e) => onFollowClick(e, issue)}
          />
        </div>
      </div>
    </Link>
  );
}

export const IssueCard = memo(IssueCardComponent);
