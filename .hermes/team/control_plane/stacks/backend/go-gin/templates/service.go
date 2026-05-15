package service

import (
	"errors"
)

type ${ClassName}Service struct {
	repo *${ClassName}Repository
}

func New${ClassName}Service(repo *${ClassName}Repository) *${ClassName}Service {
	return &${ClassName}Service{repo: repo}
}

func (s *${ClassName}Service) List() ([]${ClassName}DTO, error) {
	return s.repo.List()
}

func (s *${ClassName}Service) GetByID(id int64) (${ClassName}DTO, error) {
	item, err := s.repo.GetByID(id)
	if err != nil {
		return ${ClassName}DTO{}, errors.New("not found")
	}
	return item, nil
}

func (s *${ClassName}Service) Create(dto ${ClassName}DTO) (${ClassName}DTO, error) {
	return s.repo.Create(dto)
}

func (s *${ClassName}Service) Update(id int64, dto ${ClassName}DTO) (${ClassName}DTO, error) {
	dto.ID = id
	return s.repo.Update(dto)
}

func (s *${ClassName}Service) Delete(id int64) error {
	return s.repo.Delete(id)
}
