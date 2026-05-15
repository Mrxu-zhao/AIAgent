package ${package};

import org.springframework.web.bind.annotation.*;
import org.springframework.validation.annotation.Validated;
import lombok.RequiredArgsConstructor;
import java.util.List;

@RestController
@RequestMapping("${endpoint}")
@RequiredArgsConstructor
@Validated
public class ${ClassName}Controller {

    private final ${ClassName}Service ${className}Service;

    @GetMapping
    public List<${ClassName}DTO> list() {
        return ${className}Service.list();
    }

    @GetMapping("/{id}")
    public ${ClassName}DTO getById(@PathVariable Long id) {
        return ${className}Service.getById(id);
    }

    @PostMapping
    public ${ClassName}DTO create(@RequestBody @Valid ${ClassName}DTO dto) {
        return ${className}Service.create(dto);
    }

    @PutMapping("/{id}")
    public ${ClassName}DTO update(@PathVariable Long id, @RequestBody @Valid ${ClassName}DTO dto) {
        return ${className}Service.update(id, dto);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        ${className}Service.delete(id);
    }
}
